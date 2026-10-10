"""Install reversible user-level autostart and labwc rules. Run on the Pi."""
import argparse
import datetime
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true',help='Apply after reviewing the printed changes')
    parser.add_argument('--projection-host',action='store_true',help='Use installed Hudiy for real Android Auto and a persistent taskbar')
    args=parser.parse_args()
    if sys.platform!='linux':parser.error('Run this installer on Raspberry Pi OS')
    root=Path(__file__).resolve().parents[1]
    config=Path.home()/'.config'
    autostart=config/'labwc'/'autostart'
    rc=config/'labwc'/'rc.xml'
    launch=root/'launcher'/('hudiy_host.py' if args.projection_host else 'launcher.py')
    marker='# BEGIN HUDIY RECREATION'
    if autostart.exists():original=autostart.read_text(encoding='utf-8')
    else:
        system_autostart=Path('/etc/xdg/labwc/autostart')
        original=system_autostart.read_text(encoding='utf-8') if system_autostart.exists() else '#!/bin/sh\n'
    if marker in original:parser.error('A recreation autostart block already exists; review it before reinstalling')
    log=Path.home()/'.local/share/hudiy-recreation/launcher.log'
    if args.projection_host:
        old='$HOME/.hudiy/share/hudiy_run.sh'
        lines=original.splitlines()
        matching=[i for i,line in enumerate(lines) if line.strip()==old]
        if len(matching)!=1:parser.error('Expected exactly one documented Hudiy startup line; review autostart manually')
        lines[matching[0]]='# Original Hudiy startup is now invoked by the recreation projection host: '+old
        original='\n'.join(lines)+'\n'
    entry=original.rstrip()+'\n\n'+marker+'\n/usr/bin/python3 '+shlex.quote(str(launch))+(' --apply' if args.projection_host else '')+' >> '+shlex.quote(str(log))+' 2>&1 &\n# END HUDIY RECREATION\n'
    if rc.exists():tree=ET.parse(rc);document=tree.getroot()
    else:
        system=Path('/etc/xdg/labwc/rc.xml')
        if not system.is_file():parser.error('No labwc configuration found; do not replace session defaults with an empty file')
        tree=ET.parse(system);document=tree.getroot()
    namespace=document.tag.partition('}')[0]+'}' if document.tag.startswith('{') else ''
    if namespace:ET.register_namespace('',namespace[1:-1])
    rules=document.find(namespace+'windowRules')
    if rules is None:rules=ET.SubElement(document,namespace+'windowRules')
    identifier='hudiy' if args.projection_host else 'hudiy-recreation'
    existing=rules.find(namespace+"windowRule[@identifier='"+identifier+"']")
    if existing is not None:rules.remove(existing)
    rule=ET.SubElement(rules,namespace+'windowRule',{'identifier':identifier,'serverDecoration':'no'})
    ET.SubElement(rule,namespace+'action',{'name':'ToggleAlwaysOnTop'})
    ET.SubElement(rule,namespace+'action',{'name':'Maximize'})
    print('Install user autostart:',autostart)
    print(entry)
    print('Add labwc rule:',ET.tostring(rule,encoding='unicode'))
    print('The projection host invokes installed Hudiy after starting the recreation service.' if args.projection_host else 'Existing Hudiy autostart is not disabled; select the replacement only after acceptance testing.')
    if not args.apply:
        print('Dry run. Use --apply to save these changes.')
        return
    stamp=datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    for path in (autostart,rc):
        if path.exists():path.with_name(path.name+'.backup-'+stamp).write_bytes(path.read_bytes())
        path.parent.mkdir(parents=True,exist_ok=True)
    autostart.write_text(entry,encoding='utf-8')
    log.parent.mkdir(parents=True,exist_ok=True)
    ET.indent(tree,space='  ')
    tree.write(rc,encoding='utf-8',xml_declaration=True)
    print('Installed. Start the application manually first; the autostart entry takes effect next login.')
if __name__=='__main__':main()
