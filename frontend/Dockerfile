# Stage 1: Build Stage
FROM node:20-slim AS build-stage

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source and build for production
COPY . .
RUN npm run build

# Stage 2: Production Stage (The "Slim" Runner)
FROM nginx:alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy the build artifacts from the build-stage
# Note: Vite builds into the 'dist' folder by default
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Expose port 80 for the Nginx server
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]