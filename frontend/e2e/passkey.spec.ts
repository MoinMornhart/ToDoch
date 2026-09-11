import { expect, test } from '@playwright/test';

// Läuft nach app.spec.ts (Konto existiert). Chromium stellt einen virtuellen
// Authenticator bereit – so läuft der echte WebAuthn-Ablauf im Browser.
// Eindeutige Namen je Lauf: Bei einer Wiederholung in der CI existiert der Passkey des
// ersten Versuchs noch in der Datenbank.
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

test('Passkey hinzufügen, damit ohne Passwort anmelden und entfernen', async ({ page }) => {
	const device = `Gerät-${Date.now()}`;
	const renamed = `Laptop-${Date.now()}`;
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
	await section.getByLabel('Name', { exact: true }).fill(device);
	await section.getByLabel('Passwort zur Bestätigung').fill(PASSWORD);
	await section.getByRole('button', { name: 'Passkey hinzufügen' }).click();
	await expect(page.getByRole('status')).toContainText('Passkey hinzugefügt');
	await expect(section.getByText(device)).toBeVisible();

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

	// Frisch laden – erst dann ist sicher die neue Sitzung in Gebrauch
	await page.goto('/settings');
	await expect(page.getByRole('region', { name: 'Angemeldete Geräte' })).toContainText('Passkey');
	const row = section.getByRole('listitem').filter({ hasText: device });
	await expect(row).toContainText('zuletzt verwendet');

	// Umbenennen und entfernen
	await section.getByRole('button', { name: `Umbenennen: ${device}` }).click();
	await section.getByLabel('Name', { exact: true }).first().fill(renamed);
	await section.getByRole('button', { name: 'Speichern' }).click();
	await expect(section.getByText(renamed, { exact: true })).toBeVisible();
	await section.getByRole('button', { name: `Entfernen: ${renamed}` }).click();
	await section.getByRole('button', { name: `Entfernen: ${renamed}` }).click();
	await expect(page.getByRole('status')).toContainText('Passkey entfernt');
	await expect(section.getByText(renamed, { exact: true })).toHaveCount(0);

	expect(problems).toEqual([]);
});
