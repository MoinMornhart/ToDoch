import { defineConfig } from '@playwright/test';

const DATABASE =
	process.env.TODOCH_E2E_DATABASE_URL ??
	'postgresql+asyncpg://todoch:todoch@localhost:55432/todoch_e2e';

// Das Backend läuft mit frischer Datenbank und Redis im Speicher; das Frontend als
// Produktions-Build hinter scripts/serve.mjs (gleiche CSP wie Caddy).
export default defineConfig({
	testDir: 'e2e',
	fullyParallel: false,
	workers: 1,
	retries: process.env.CI ? 1 : 0,
	reporter: process.env.CI ? 'github' : 'list',
	use: { baseURL: 'http://localhost:4173', trace: 'retain-on-failure', locale: 'de-DE' },
	webServer: [
		{
			command:
				'uv run alembic downgrade base && uv run alembic upgrade head && uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000',
			cwd: '../backend',
			url: 'http://127.0.0.1:8000/api/health',
			reuseExistingServer: false,
			timeout: 120_000,
			env: {
				TODOCH_ENVIRONMENT: 'test',
				TODOCH_ORIGIN: 'http://localhost:4173',
				TODOCH_SECRET_KEY: 'e2e-secret-key-0123456789-abcdefghijklmnop',
				TODOCH_ENCRYPTION_KEYS: '1:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=',
				TODOCH_DATABASE_URL: DATABASE,
				TODOCH_REDIS_URL: 'memory://',
				TODOCH_SETUP_TOKEN: 'e2e-setup-code-123456'
			}
		},
		{
			command: 'npm run build && node scripts/serve.mjs',
			url: 'http://localhost:4173',
			reuseExistingServer: false,
			timeout: 240_000,
			env: { PORT: '4173', TODOCH_BACKEND: 'http://127.0.0.1:8000' }
		}
	],
	projects: [{ name: 'chromium', use: { browserName: 'chromium' } }]
});
