import assert from 'node:assert/strict';
import test from 'node:test';
import { CONTACT_FILTERS, contactGroup, filterContacts } from '../src/contactFilters.js';

test('every name belongs to one touch filter, including accents and unnamed entries', () => {
  const entries = [
    { name: '  Änne' }, { name: 'Émile' }, { name: 'Łukasz' },
    { name: 'Günther' }, { name: 'Momo' }, { name: 'Özil' },
    { name: 'Šara' }, { name: 'ßurname' }, { name: 'Zoe' },
    { name: '+436000' }, { name: '李' }, { name: '' }, {},
  ];
  assert.deepEqual(entries.map(contactGroup), ['A–F', 'A–F', '#', 'G–L', 'M–R', 'M–R', 'S–Z', 'S–Z', 'S–Z', '#', '#', '#', '#']);
  const grouped = CONTACT_FILTERS.slice(1).flatMap(group => filterContacts(entries, group));
  assert.equal(grouped.length, entries.length);
  assert.equal(new Set(grouped).size, entries.length);
});

test('filtering preserves phone order, number data and the complete All view', () => {
  const entries = Object.freeze([
    Object.freeze({ name: 'Rony', numbers: Object.freeze(['123', '456']), date: 'Today' }),
    Object.freeze({ name: 'Anna', numbers: Object.freeze(['789']) }),
    Object.freeze({ name: 'Momo', numbers: Object.freeze(['012']) }),
  ]);
  assert.equal(filterContacts(entries, 'All'), entries);
  assert.deepEqual(filterContacts(entries, 'M–R'), [entries[0], entries[2]]);
  assert.deepEqual(filterContacts(entries, '#'), []);
});
