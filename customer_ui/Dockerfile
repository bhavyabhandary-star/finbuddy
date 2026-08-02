# Static customer UI (React PWA, no build step -- React/Babel loaded via
# CDN) -- nginx serving static files, no backend of its own (calls the two
# API Spaces directly from the browser via CORS). Build context is this
# directory, same self-contained pattern as the other two services'
# Dockerfiles.
#
# Port 8080, not nginx's default 80: HF Spaces rejects app_port < 1025
# ("must be greater than or equal to 1025") -- found via a real failed
# deploy, not assumed.
FROM nginx:alpine
COPY index.html manifest.json icon.svg sw.js /usr/share/nginx/html/
RUN sed -i 's/listen\s*80;/listen 8080;/' /etc/nginx/conf.d/default.conf
EXPOSE 8080
