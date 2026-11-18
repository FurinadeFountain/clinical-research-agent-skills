/**
 * Reusable browser-side helpers for reading and updating Notion pages via `/api/v3/*`
 * when the native Notion MCP connector is unavailable and a shared browser (`preview_evaluate`) is used.
 *
 * Usage inside `preview_evaluate`:
 *   1. `dumpNotionPageCompact(pageId)` — fetches the entire page and all nested table rows in 2 requests,
 *      stripping `crdt_data` and permissions so the payload stays small (<15 KB) and never triggers context bloat.
 *   2. `applyNotionUpdates({ spaceId, pageId, textUpdates, tableRowReplacements, removeIds })` —
 *      separates text-block `title` updates from CRDT `table_row` atomic replacements so `table_row`
 *      validation never rolls back prose edits.
 */

async function dumpNotionPageCompact(pageId) {
  const chunk = await fetch("/api/v3/loadPageChunk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pageId,
      limit: 100,
      cursor: { stack: [] },
      chunkNumber: 0,
      verticalColumns: false
    })
  }).then(r => r.json());

  const blockMap = chunk.recordMap?.block || {};
  const pageVal = blockMap[pageId]?.value?.value || blockMap[pageId]?.value;
  const spaceId = pageVal?.space_id;
  const contentIds = pageVal?.content || [];

  // Fetch all top-level blocks in a single batch
  const sync1 = await fetch("/api/v3/syncRecordValues", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      requests: contentIds.map(id => ({ pointer: { table: "block", id, spaceId }, version: -1 }))
    })
  }).then(r => r.json());

  const allBlocks = { ...blockMap, ...(sync1.recordMap?.block || {}) };

  // Collect any child row IDs from tables/callouts
  const childIds = [];
  for (const id of contentIds) {
    const b = allBlocks[id]?.value?.value || allBlocks[id]?.value;
    if (b?.content?.length) {
      childIds.push(...b.content);
    }
  }

  if (childIds.length > 0) {
    const sync2 = await fetch("/api/v3/syncRecordValues", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        requests: childIds.map(id => ({ pointer: { table: "block", id, spaceId }, version: -1 }))
      })
    }).then(r => r.json());
    Object.assign(allBlocks, sync2.recordMap?.block || {});
  }

  const blocks = contentIds.map((id, idx) => {
    const b = allBlocks[id]?.value?.value || allBlocks[id]?.value;
    const item = {
      idx,
      id,
      type: b?.type,
      title: b?.properties?.title || []
    };
    if (b?.content?.length) {
      item.children = b.content.map(cid => {
        const cb = allBlocks[cid]?.value?.value || allBlocks[cid]?.value;
        return {
          id: cid,
          type: cb?.type,
          properties: cb?.properties || {}
        };
      });
    }
    return item;
  });

  return { spaceId, pageId, count: contentIds.length, blocks };
}

async function applyNotionUpdates({
  spaceId,
  pageId,
  textUpdates = [],          // Array of { id, title: richTextArray }
  removeIds = [],            // Array of block IDs to remove from page content
  tableRowReplacements = []  // Array of { tableId, oldRowId, properties }
}) {
  const now = Date.now();
  const results = {};

  // Transaction 1: Prose blocks (title updates + block removals)
  const proseOps = [];
  for (const u of textUpdates) {
    proseOps.push(
      { id: u.id, table: "block", path: ["properties", "title"], command: "set", args: u.title },
      { id: u.id, table: "block", path: ["last_edited_time"], command: "set", args: now }
    );
  }
  for (const rid of removeIds) {
    proseOps.push(
      { id: pageId, table: "block", path: ["content"], command: "listRemove", args: { id: rid } },
      { id: rid, table: "block", path: ["alive"], command: "set", args: false },
      { id: rid, table: "block", path: ["last_edited_time"], command: "set", args: now }
    );
  }

  if (proseOps.length > 0) {
    const res1 = await fetch("/api/v3/saveTransactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        requestId: crypto.randomUUID(),
        transactions: [{ id: crypto.randomUUID(), spaceId, operations: proseOps }]
      })
    });
    results.proseStatus = res1.status;
    if (!res1.ok) {
      results.abortedAfterProseFailure = true;
      return results;
    }
  }

  // Transaction 2: Atomic replacement of CRDT table_row blocks
  const rowOps = [];
  for (const r of tableRowReplacements) {
    const newId = crypto.randomUUID();
    rowOps.push(
      {
        id: newId,
        table: "block",
        path: [],
        command: "set",
        args: {
          id: newId,
          type: "table_row",
          version: 1,
          properties: r.properties,
          created_time: now,
          last_edited_time: now,
          parent_id: r.tableId,
          parent_table: "block",
          alive: true,
          space_id: spaceId
        }
      },
      { id: r.tableId, table: "block", path: ["content"], command: "listAfter", args: { after: r.oldRowId, id: newId } },
      { id: r.tableId, table: "block", path: ["content"], command: "listRemove", args: { id: r.oldRowId } },
      { id: r.oldRowId, table: "block", path: ["alive"], command: "set", args: false }
    );
  }

  if (rowOps.length > 0) {
    const res2 = await fetch("/api/v3/saveTransactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        requestId: crypto.randomUUID(),
        transactions: [{ id: crypto.randomUUID(), spaceId, operations: rowOps }]
      })
    });
    results.tableStatus = res2.status;
  }

  return results;
}
