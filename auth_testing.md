# Auth Testing Playbook (AI Video Studio)

## Auth flow
- Frontend button redirects to `https://auth.emergentagent.com/?redirect=<origin>/auth/callback`.
- Callback URL receives `#session_id=<id>` fragment.
- Frontend POSTs `session_id` to backend `/api/auth/session` which calls Emergent
  `/auth/v1/env/oauth/session-data`, stores user + session in Mongo and sets a
  `session_token` httpOnly cookie.
- All protected routes validate the cookie via `/api/auth/me`.

## Direct session injection (for automated testing)
```bash
mongosh --eval "
use('test_database');
var uid = 'user_' + Date.now();
var tok = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: uid,
  email: 'test.user@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/128',
  role: 'user',
  credits: 5,
  plan: 'free',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: uid,
  session_token: tok,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('SESSION=' + tok);
print('UID=' + uid);
"
```

Attach the returned token either as cookie `session_token` or header
`Authorization: Bearer <token>`.
