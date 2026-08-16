# discord-badge-spoofer

inflates the discord "hours played" and "games played" profile badges by posting
`launch_game` and `running_game_heartbeat` events to `/api/v9/science` - the same
analytics endpoint the real client uses to credit playtime. `launch_game` registers
a game as played and `duration_tracked_ms` adds the hours, and neither is validated,
so any number goes straight through.

## setup

1. run it:
   ```
   python spoofer.py
   ```

2. first run asks for your discord account token. paste it and it gets saved to
   `science_state.json` (reused after that).

3. it also needs a cookie. pick option `3 refresh auth`, then paste the full
   `cookie` header from any `/science` request in devtools (network tab). it gets
   saved to `science_state.json` too.

## menu

- `1` claim playtime - asks for hours per game, applies to every game
- `2` games played - marks every game as played (1 minute each)
- `3` refresh auth - pulls a fresh analytics token and lets you update the cookie
- `4` exit

## how auth works

- `token` - your account token, entered on first run, saved to `science_state.json`
- `analytics_token` - pulled from the gateway ready payload automatically
- `super_props` / heartbeat / launch ids - generated automatically
- `cookie` (cf_clearance) - pasted by hand, via option `3`
- `fingerprint` - optional, only needed for the games-played count (see below)

badges update on discord's analytics cycle, so give it a day.

## the games-played count needs a fingerprint

hours come straight from the heartbeats and work with just token + cookie. the
games-played **count** is different: each `launch_game` carries an
`executable_fingerprint`, and discord likely only credits the count when it's a
real one.

what we found reverse-engineering it:

- it's computed by discord's native module (`discord_utils.node`) from the running
  game's exe bytes, **scoped to your user id**. it can't be fabricated - a made-up
  value is accepted at ingestion (204) but almost certainly ignored for the count.
- so it's per-user. there's no shipping a working one; you capture your own.
- hours are unaffected either way (heartbeats have no fingerprint) - unless hours
  also depend on the `launch_game` somehow, which we haven't verified yet.

if `fingerprint` isn't set in `science_state.json`, the tool warns on startup and
simply omits the field - hours still work, the count just won't move. to set one,
paste a real `executable_fingerprint` (captured from a `launch_game` request in
your own client's devtools) into `science_state.json`:

```json
{ "fingerprint": "Ab5ekw..." }
```

## disclaimer

this breaks discord's terms of service. use it on accounts you're fine losing.
provided as-is with no warranty.

## license

released under the mit license. see [LICENSE](LICENSE).
