FROM node:18-alpine

WORKDIR /app

# Copy package configurations
COPY package.json ./

# Install dependencies (fallback to npm install if lockfile missing)
RUN npm install

# Copy application files
COPY . .

# Expose Next.js port
EXPOSE 3000

# Start server in development mode
CMD ["npm", "run", "dev"]
