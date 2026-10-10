"""Reversibly select our independent car app for labwc graphical startup."""
import argparse
import datetime
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

BEGIN='# BEGIN HUDIY RECREATION'
END='# END HUDIY RECREATION'


def replace_startup(original,launch,log):
    if BEGIN in original or END in original:
        if original.count(BEGIN)!=1 or original.count(END)!=1 or original.index(END)<original.index(BEGIN):
            raise ValueError('Malformed existing recreation startup block')
        before,_,tail=original.partition(BEGIN)
        _,_,after=tail.partition(END)
        original=before.rstrip()+'\n'+after.lstrip('\n')
    lines=original.splitlines()
    for index,line in enumerate(lines):
        if line.strip()=='$HOME/.hudiy/share/hudiy_run.sh':
            lines[index]='# Previous dashboard startup retained for recovery: '+line.strip()
        elif line.strip().startswith('python3 /home/noriel/hudiy-examples/examples/obd_charts/charts.py '):
            lines[index]='# Previous Hudiy OBD example retained for recovery: '+line.strip()
    return '\n'.join(lines).rstrip()+'\n\n'+BEGIN+'\n/usr/bin/python3 '+shlex.quote(str(launch))+' >> '+shlex.quote(str(log))+' 2>&1 &\n'+END+'\n'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if sys.platform!='linux':parser.error('Run on the Pi')
    root=Path(__file__).resolve().parents[1]
    if not (root/'native/build/hudiy-car-runtime').is_file():parser.error('Build and test the native runtime before selecting it for startup')
    config=Path.home()/'.config/labwc'
    autostart=config/'autostart';rc=config/'rc.xml'
    fallback=Path('/etc/xdg/labwc')
    source=autostart if autostart.exists() else fallback/'autostart'
    original=source.read_text() if source.exists() else '#!/bin/sh\n'
    log=Path.home()/'.local/share/hudiy-recreation/standalone.log'
    try:entry=replace_startup(original,root/'launcher/launcher.py',log)
    except ValueError as error:parser.error(str(error))
    tree=ET.parse(rc if rc.exists() else fallback/'rc.xml');document=tree.getroot()
    namespace=document.tag.partition('}')[0]+'}' if document.tag.startswith('{') else ''
    if namespace:ET.register_namespace('',namespace[1:-1])
    rules=document.find(namespace+'windowRules')
    if rules is None:rules=ET.SubElement(document,namespace+'windowRules')
    for rule in list(rules):
        if rule.get('identifier')=='hudiy-recreation':rules.remove(rule)
    rule=ET.SubElement(rules,namespace+'windowRule',{'identifier':'hudiy-recreation','serverDecoration':'no'})
    ET.SubElement(rule,namespace+'action',{'name':'ToggleAlwaysOnTop'})
    ET.SubElement(rule,namespace+'action',{'name':'Maximize'})
    print(entry)
    print('Native labwc rule:',ET.tostring(rule,encoding='unicode'))
    if not args.apply:return
    stamp=datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    config.mkdir(parents=True,exist_ok=True)
    for path in (autostart,rc):
        if path.exists():path.with_name(path.name+'.backup-'+stamp).write_bytes(path.read_bytes())
    autostart.write_text(entry)
    ET.indent(tree,space='  ');tree.write(rc,encoding='utf-8',xml_declaration=True)
    log.parent.mkdir(parents=True,exist_ok=True)
    print('Independent application selected for the next graphical login. Backups retained.')

if __name__=='__main__':main()
