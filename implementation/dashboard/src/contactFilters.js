export const CONTACT_FILTERS = ['All', 'A–F', 'G–L', 'M–R', 'S–Z', '#'];

export function contactGroup(entry) {
  const name = String(entry.name || '').trim().normalize('NFD')
    .replace(/\p{M}/gu, '').replace(/ß/gi, 'S').toUpperCase();
  const first = name.match(/[\p{L}\p{N}]/u)?.[0] || '';
  if (/^[A-F]$/.test(first)) return 'A–F';
  if (/^[G-L]$/.test(first)) return 'G–L';
  if (/^[M-R]$/.test(first)) return 'M–R';
  if (/^[S-Z]$/.test(first)) return 'S–Z';
  return '#';
}

export function filterContacts(entries, group) {
  return group === 'All' ? entries : entries.filter(entry => contactGroup(entry) === group);
}
