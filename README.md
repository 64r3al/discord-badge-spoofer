# discord-badge-spoofer

inflates the discord "hours played" and "games played" profile badges by posting
`running_game_heartbeat` events to `/api/v9/science` - the same analytics endpoint
the real client uses to credit playtime. `duration_tracked_ms` isn't validated, so
any number goes straight through.

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
- `cookie` (cf_clearance) - the only value you paste by hand

badges update on discord's analytics cycle, so give it a day.

## disclaimer

this breaks discord's terms of service. use it on accounts you're fine losing.
provided as-is with no warranty.
