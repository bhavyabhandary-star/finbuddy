---
title: FinBuddy
emoji: 💳
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 8080
pinned: false
---

# FinBuddy — Customer UI

The real customer-facing credit-assessment and coaching page, calling the live
`finbuddy-scoring` and `finbuddy-rag-coach` Spaces directly from the browser (CORS
enabled on both). Replaces the earlier Claude-Design-generated prototype
(subtle-sable-d3376b.netlify.app), which was still wired to the original
hackathon's hardcoded n8n mock data -- this one has no fabricated content: every
number and factor shown comes from a real API call to a real trained model or a
real Groq-generated, corpus-grounded answer.

A real installable PWA (manifest + service worker), built as React loaded via CDN
(no build step, still a single deployable static directory) -- not the earlier
plain-JS version. The static app shell is cached for offline load; every API call
(score, coach) always goes to the network, never cached, since that data must
always be live.
