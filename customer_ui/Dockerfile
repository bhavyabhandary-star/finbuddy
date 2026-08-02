# Static single-file customer UI -- nginx serving index.html, nothing else
# needed (no build step, no backend; it calls the two API Spaces directly
# from the browser via CORS). Build context is this directory, same
# self-contained pattern as the other two services' Dockerfiles.
FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 80
