import { expect, test } from '@playwright/test';

// Läuft nach app.spec.ts (Konto existiert). Chromium stellt einen virtuellen
// Authenticator bereit – so läuft der echte WebAuthn-Ablauf im Browser.
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

test('Passkey hinzufügen, damit ohne Passwort anmelden und entfernen', async ({ page }) => {
	const problems: string[] = [];
	page.on('console', (m) => {
		if (/content security policy|refused to|permissions policy/i.test(m.text()))
			problems.push(m.text());
	});
	page.on('pageerror', (e) => problems.push(e.message));

	const cdp = await page.context().newCDPSession(page);
	await cdp.send('WebAuthn.enable');
	await cdp.send('WebAuthn.addVirtualAuthenticator', {
		options: {
			protocol: 'ctap2',
			transport: 'internal',
			hasResidentKey: true,
			hasUserVerification: true,
			isUserVerified: true,
			automaticPresenceSimulation: true
		}
	});

	await page.goto('/login');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
	await expect(page).toHaveURL(/\/$/);

	await page.getByRole('link', { name: 'Einstellungen' }).first().click();
	const section = page.getByRole('region', { name: 'Passkeys' });
	await expect(section.getByText('Noch keine Passkeys.')).toBeVisible();
	await section.getByLabel('Name', { exact: true }).fill('Test-Gerät');
	await section.getByLabel('Passwort zur Bestätigung').fill(PASSWORD);
	await section.getByRole('button', { name: 'Passkey hinzufügen' }).click();
	await expect(page.getByRole('status')).toContainText('Passkey hinzugefügt');
	await expect(section.getByText('Test-Gerät')).toBeVisible();

	// Abmelden und mit dem Passkey wieder anmelden – ohne E-Mail und Passwort
	await page.getByRole('button', { name: 'Abmelden' }).first().click();
	await expect(page).toHaveURL(/\/login$/);
	// Der virtuelle Authenticator beantwortet mitunter schon die stille Autofill-Anfrage
	await page
		.getByRole('button', { name: 'Mit Passkey anmelden' })
		.click({ timeout: 5000 })
		.catch(() => undefined);
	await expect(page).toHaveURL(/\/$/);
	await expect(page.getByRole('heading', { level: 1 })).toContainText('Admin');

	await page.getByRole('link', { name: 'Einstellungen' }).first().click();
	await expect(page.getByRole('region', { name: 'Angemeldete Geräte' })).toContainText('Passkey');
	await expect(section).toContainText('zuletzt verwendet');

	// Umbenennen und entfernen
	await section.getByRole('button', { name: 'Umbenennen: Test-Gerät' }).click();
	await section.getByLabel('Name', { exact: true }).first().fill('Laptop');
	await section.getByRole('button', { name: 'Speichern' }).click();
	await expect(section.getByText('Laptop', { exact: true })).toBeVisible();
	await section.getByRole('button', { name: 'Entfernen: Laptop' }).click();
	await section.getByRole('button', { name: 'Entfernen: Laptop' }).click();
	await expect(section.getByText('Noch keine Passkeys.')).toBeVisible();

	expect(problems).toEqual([]);
});
