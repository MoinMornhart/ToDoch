import { expect, test } from '@playwright/test';

// Läuft nach app.spec.ts (Konto existiert). Ohne echten Mailserver: Formular und Vorschläge.
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

test('Bereich „E-Mail“: Postfach einbinden mit Servervorschlag', async ({ page }) => {
	const problems: string[] = [];
	page.on('console', (m) => {
		if (/content security policy|refused to/i.test(m.text())) problems.push(m.text());
	});
	page.on('pageerror', (e) => problems.push(e.message));

	await page.goto('/login');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
	await expect(page).toHaveURL(/\/$/);

	await page.getByRole('link', { name: 'E-Mail', exact: true }).first().click();
	await expect(page).toHaveURL(/\/mail$/);
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('E-Mail');
	const accounts = page.getByRole('region', { name: 'Postfächer' });

	// Bekannter Anbieter: Server wird vorgeschlagen, Hinweis auf App-Passwort
	await accounts.getByLabel('E-Mail-Adresse', { exact: true }).fill('max@gmail.com');
	await expect(accounts.getByLabel('IMAP-Server')).toHaveValue('imap.gmail.com');
	await expect(accounts.getByLabel('Port')).toHaveValue('993');
	await expect(accounts).toContainText('App-Passwort');

	// STARTTLS stellt den Port um; von Hand geänderter Server bleibt stehen
	await accounts.getByLabel('Verschlüsselung').selectOption('starttls');
	await expect(accounts.getByLabel('Port')).toHaveValue('143');
	await accounts.getByLabel('IMAP-Server').fill('mail.example.org');
	await accounts.getByLabel('E-Mail-Adresse', { exact: true }).fill('max@gmx.de');
	await expect(accounts.getByLabel('IMAP-Server')).toHaveValue('mail.example.org');

	expect(problems).toEqual([]);
});
