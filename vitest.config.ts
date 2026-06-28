import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig( {
    plugins: [ react() ],
    test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: [ './src/test/setup.ts' ],
        // Only run frontend component/unit tests; Python tests run under pytest.
        include: [ 'src/**/*.{test,spec}.{ts,tsx}' ],
    },
} );
