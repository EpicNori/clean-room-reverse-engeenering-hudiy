import React, { useEffect, useRef, useState } from 'react';
import { CONTACT_FILTERS, filterContacts } from './contactFilters';

const titles = { contacts: 'Contacts', favorites: 'Favorites', 'call-log': 'Call log' };

export function PhonebookView({ view, data, refresh, select, settings }) {
  const [group, setGroup] = useState('All');
  const [shown, setShown] = useState(200);
  const list = useRef(null);
  useEffect(() => { setGroup('All'); setShown(200); }, [view]);
  useEffect(() => { if (list.current) list.current.scrollTop = 0; }, [view, group]);
  const book = data.views?.[view] || { entries: [] };
  const entries = filterContacts(book.entries || [], group);
  return (
    <div className="phonebook-view">
      <header>
        <h1>{titles[view]}</h1>
        <div className="phonebook-actions"><button className="phonebook-refresh" aria-label="Contacts settings" onClick={settings}>
          <span className="material-symbols-rounded" aria-hidden="true">settings</span>
        </button><button className="phonebook-refresh" onClick={refresh} disabled={data.syncing}>
          <span className="material-symbols-rounded" aria-hidden="true">refresh</span>
          {data.syncing ? 'Syncing' : 'Refresh'}
        </button></div>
      </header>
      <p className="phonebook-status" role="status">
        {data.error || book.error || (data.updatedAt
          ? `${data.name || 'Phone'} · ${entries.length} of ${(book.entries || []).length} entries`
          : 'Connect your phone by Bluetooth and allow contact sharing')}
      </p>
      <div className="phonebook-filters" role="group" aria-label="Filter by name">
        {CONTACT_FILTERS.map(value => <button key={value} aria-pressed={group === value}
          aria-label={value === '#' ? 'Other names and numbers' : value}
          onClick={() => { setGroup(value); setShown(200); }}>{value}</button>)}
      </div>
      <div className="phonebook-list" ref={list}>
        {entries.slice(0, shown).map((entry, index) => (
          <button className="phonebook-entry" key={`${index}-${entry.numbers[0]}`} onClick={() => select(entry.numbers[0])}>
            <span className="material-symbols-rounded phonebook-avatar" aria-hidden="true">
              {view === 'call-log' ? 'history' : 'person'}
            </span>
            <span><strong>{entry.name}</strong><small>{entry.numbers.join(' · ')}{entry.date ? ` · ${entry.date}` : ''}</small></span>
            <span className="material-symbols-rounded" aria-hidden="true">dialpad</span>
          </button>
        ))}
        {!entries.length && <p>{group !== 'All' ? 'No entries in this group' : data.syncing ? 'Loading from your phone…' : 'No entries provided by the phone'}</p>}
        {entries.length > shown && <button className="phonebook-more" onClick={() => setShown(count => count + 200)}>Show more</button>}
      </div>
    </div>
  );
}
