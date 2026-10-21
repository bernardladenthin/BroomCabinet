// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

// Dumps Microsoft To Do's own IndexedDB into one JSON file. Paste into the browser console
// (F12) on https://to-do.live.com/tasks/ after the lists have loaded.
//
// READ-ONLY: it opens the database, reads the stores below with getAll() and closes it again.
// No request leaves the browser; the file is handed to the browser's download.
//
// LEFT OUT ON PURPOSE: the stores `sync` and `settings` (client state), and each list's
// `sharing_link` and `invitation_token` -- whoever holds those can join a shared list.
(async () => {
  const names = (await indexedDB.databases()).map(d => d.name).filter(n => /^todo_/.test(n));
  if (names.length !== 1) throw new Error('expected exactly one todo_* database, found: ' + names.join(', '));
  const db = await new Promise((res, rej) => {
    const r = indexedDB.open(names[0]);
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
  const all = n => new Promise((res, rej) => {
    const q = db.transaction(n, 'readonly').objectStore(n).getAll();
    q.onsuccess = () => res(q.result);
    q.onerror = () => rej(q.error);
  });
  const data = {exported_at: new Date().toISOString(), source: 'to-do.live.com IndexedDB ' + db.name + ' v' + db.version};
  for (const n of ['listGroups', 'lists', 'tasks', 'steps', 'linkedEntities', 'categories', 'members', 'assignments']) {
    data[n] = db.objectStoreNames.contains(n) ? await all(n) : [];
  }
  db.close();
  data.lists = data.lists.map(l => { const c = {...l}; delete c.sharing_link; delete c.invitation_token; return c; });
  const blob = new Blob([JSON.stringify(data, null, 2) + '\n'], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'MicrosoftTODO-export-' + data.exported_at.slice(0, 10) + '.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  // compare these with the counters in the app's sidebar before going on
  console.log({bytes: blob.size, lists: data.lists.length, tasks: data.tasks.length,
               open: data.tasks.filter(t => !t.completed).length, attachments: data.linkedEntities.length,
               steps: data.steps.length});
})();
