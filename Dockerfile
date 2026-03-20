# Step 1: Build the React application
FROM node:20-slim AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Step 2: Serve using Nginx
FROM nginx:alpine
# Copy the built assets from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose Nginx default port
EXPOSE 80

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
