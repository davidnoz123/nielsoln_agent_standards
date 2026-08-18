# Profile: python-chrome-cdp

Python code that controls Chrome via the Chrome DevTools Protocol (CDP).

**Repos using this profile:** `soc_med_mirror`, `video_annotation`, `chrome_tools`

---

## Purpose

Chrome is launched and controlled via CDP for automation, recording, and annotation tasks. Multiple
processes sharing the same Chrome debugging WebSocket is a known silent failure mode.

---

## Rules

### Never open a competing CDPClient

Chrome allows multiple processes to connect to the same debugging WebSocket without error, causing
silent cross-talk. Guard against this:

```python
if _port_open(_SERVER_PORT):
    raise RuntimeError(
        "annotation server is running — use server mode, not direct CDPClient"
    )
```

`SingletonProcess` only guards `AppRuntime` — ad-hoc scripts must add this check themselves.

### Observe through the network, act through the DOM

**Never read a fact off the rendered page when the network carries the same
fact.** The DOM is a rendering; the network is the event. A rendering has only
heuristics about when it stopped changing, and every one of them is somebody
else's implementation detail.

Measured over a single day of work on `stock_capture`, 2026-08-17:

| approach | outcome |
|---|---|
| CDP `Network` capture | every question answered first time, and several re-answered later from stored captures without reopening the browser |
| DOM scraping for "has the reply finished" | four distinct bugs, three fixes, still wrong for long replies |

The four were: length-stability returning a `Thinking` placeholder as an answer;
a `data-is-streaming` attribute going false eighteen seconds before the reply
ended; a stop button that is absent *while the model is thinking*; and a helper
that returned the previous turn's text twice in a row because of the first three.
Each fix was another heuristic. The network stream has an end.

**Three properties the DOM does not have:**

1. **It is self-describing.** When a JSON field renames, the parse fails loudly
   and the payload is in hand. When an attribute changes meaning, nothing
   announces it -- the attribute still exists and still has a value.
2. **It can be archived and re-analysed.** A capture answers questions asked days
   later. A DOM is gone the moment the page re-renders.
3. **Repair is local.** A broken selector yields nothing and must be
   reverse-engineered by inspection; a broken parse comes with the bytes that
   broke it.

**The boundary:** interaction is irreducibly DOM. Focus the composer, click the
button, set the file input -- a rich-text editor will ignore an `insertText` into
an unfocused document, and no amount of network watching changes that. The rule
is about *observation*, not actuation.

**Observing from a second client is fine; driving from two is not.** Measured
2026-08-17: a `NetworkMonitor` in one client captured 66 events while a second
client sent a prompt through the same tab, and both succeeded. The harm the rule
above describes is two clients *acting* on one target -- one typing while the
other reads. Passive capture alongside actuation is not that, and `NetworkMonitor`
opens its own client by design, with no way to pass one in.

**The completion signal is the stream ending, not anything on the page.** These
chat interfaces stream over `fetch()` with a `text/event-stream` body rather than
the `EventSource` API, so `Network.eventSourceMessageReceived` never fires. Watch
for `Network.responseReceived` with `mimeType == "text/event-stream"`, then
`Network.loadingFinished` for that same `requestId`. The reply text reassembles
from the `content_block_delta` events in the body, which is cleaner than the
rendered text -- no thinking preamble, no private-use glyphs, no markdown round
trip.

**Fetch response bodies as they arrive, not at the end.** Chrome evicts them from
its buffer as it goes; collecting at the end of a long capture returns nothing
for most of it, and the empty rows look like uninteresting endpoints rather than
lost data. Append each record to disk immediately -- a capture held in memory is
lost to whatever goes wrong next, and a formatting bug in a print loop has
already destroyed one.

**Chrome omits `postData` for larger request bodies**, setting `hasPostData`
instead. A capture that reads only `request.postData` records what was asked for
and not how to ask it.

### Never discard CDP responses silently

CDP errors are returned as `exceptionDetails` inside the response dict, not as Python exceptions:

```python
result = session.send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
exc = result.get("exceptionDetails")
if exc:
    desc = exc.get("exception", {}).get("description", str(exc))
    raise RuntimeError(f"JS exception: {desc}")
```

### Always launch Chrome with `headless=False`

Headless mode hides modal dialogs and makes debugging very difficult. Always use visible Chrome.

### Chrome must already be running before connecting

Do not launch a new Chrome instance if one is already running on the target port. Check first and
reuse the existing instance.

---

## Patterns

- `CDPClient` is loaded via `versholn.importx("chrome_tools.CDPClient")` — never at module level.
- Port-open check before creating any CDPClient.
- Always check `exceptionDetails` in CDP responses.
- `ChromeLauncher.start()` with `headless=False`.

---

## Anti-patterns

- `headless=True` for any automation (not just debugging).
- Silently ignoring `exceptionDetails` in CDP responses.
- Opening multiple CDPClient instances on the same port.
- Importing `chrome_tools` at module level.
- Reading a reply, a status or a completion signal off the DOM when the
  network carries it.
- Collecting response bodies at the end of a capture rather than on arrival.
