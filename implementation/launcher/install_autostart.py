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


def car_session_startup(launch, log):
    return ("#!/bin/sh\n"
        "timeout 5s dbus-update-activation-environment --systemd WAYLAND_DISPLAY DISPLAY >/dev/null 2>&1\n"
        "if command -v kanshi >/dev/null 2>&1; then kanshi >/dev/null 2>&1 & fi\n"
        "if [ -x /usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1 ]; then /usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1 >/dev/null 2>&1 &\n"
        "elif command -v lxpolkit >/dev/null 2>&1; then lxpolkit >/dev/null 2>&1 & fi\n"
        "/usr/bin/python3 " + shlex.quote(str(launch)) + " --boot-session >> " + shlex.quote(str(log)) + " 2>&1 &\n")


def recovery_startup(entry, fallback):
    # Both are the existing ordinary user's shell startup, never run as root.
    before, separator, tail = entry.partition(BEGIN)
    if separator:
        _, ending, after = tail.partition(END)
        if not ending: raise ValueError('Malformed managed startup')
        entry = before.rstrip() + '\n' + after.lstrip('\n')
    if fallback.strip() and fallback.strip() not in entry:
        # Disable the old proprietary/external car entries before recovery too.
        fallback = replace_startup(fallback, Path('/unused'), Path('/unused')).partition(BEGIN)[0]
        entry = fallback.rstrip() + '\n' + entry
    return entry


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
    session_entry=car_session_startup(root/'launcher/launcher.py',log)
    fallback_entry=(fallback/'autostart').read_text() if (fallback/'autostart').exists() else ''
    recovery_entry=recovery_startup(entry,fallback_entry)
    print(entry)
    print('Dedicated black session:',session_entry)
    print('Native labwc rule:',ET.tostring(rule,encoding='unicode'))
    if not args.apply:return
    stamp=datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    config.mkdir(parents=True,exist_ok=True)
    for path in (autostart,rc):
        if path.exists():path.with_name(path.name+'.backup-'+stamp).write_bytes(path.read_bytes())
    from install_pi import write_user_file
    car_config=Path.home()/'.config/hudiy-recreation/labwc'
    write_user_file(car_config/'autostart',session_entry)
    write_user_file(car_config/'rc.xml',ET.tostring(document,encoding='unicode'))
    write_user_file(car_config/'desktop-recovery',recovery_entry)
    (car_config/'desktop-recovery').chmod(0o700)
    if (config/'environment').is_file():write_user_file(car_config/'environment',(config/'environment').read_text())
    autostart.write_text(entry)
    ET.indent(tree,space='  ');tree.write(rc,encoding='utf-8',xml_declaration=True)
    log.parent.mkdir(parents=True,exist_ok=True)
    print('Independent application selected for the next graphical login. Backups retained.')

if __name__=='__main__':main()
