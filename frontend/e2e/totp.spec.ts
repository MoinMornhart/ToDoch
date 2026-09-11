import { createHmac } from 'node:crypto';
import { expect, test } from '@playwright/test';

// Läuft zuletzt (Konto aus app.spec.ts) und schaltet Zwei-Faktor am Ende wieder ab.
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

function base32(secret: string): Buffer {
	const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
	let bits = '';
	for (const char of secret.replace(/=+$/, '').toUpperCase()) {
		bits += alphabet.indexOf(char).toString(2).padStart(5, '0');
	}
	const bytes = [];
	for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
	return Buffer.from(bytes);
}

/** TOTP nach RFC 6238 – ``offset`` in 30-Sekunden-Schritten. */
function totp(secret: string, offset = 0): string {
	const counter = Math.floor(Date.now() / 30_000) + offset;
	const buffer = Buffer.alloc(8);
	buffer.writeBigUInt64BE(BigInt(counter));
	const hash = createHmac('sha1', base32(secret)).update(buffer).digest();
	const start = hash[hash.length - 1]! & 0xf;
	return ((hash.readUInt32BE(start) & 0x7fffffff) % 1_000_000).toString().padStart(6, '0');
}

test('Zwei-Faktor einrichten, damit anmelden und mit Wiederherstellungscode abschalten', async ({
	page
}) => {
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

	await page.goto('/settings');
	const section = page.getByRole('region', { name: 'Zwei-Faktor (Authenticator-App)' });
	await expect(section).toContainText('Nicht eingerichtet.');
	await section.getByLabel('Passwort zur Bestätigung').fill(PASSWORD);
	await section.getByRole('button', { name: 'Einrichten' }).click();
	const secret = (await section.getByTestId('totp-secret').textContent())!.trim();
	await expect(section.locator('svg.segno')).toBeVisible();
	await section.getByLabel('Code aus der App').fill(totp(secret));
	await section.getByRole('button', { name: 'Bestätigen' }).click();
	const codes = section.getByTestId('recovery-code');
	await expect(codes).toHaveCount(10);
	const recovery = (await codes.first().textContent())!.trim();
	await section.getByRole('button', { name: 'Ich habe sie gesichert' }).click();
	await expect(section).toContainText('10 Wiederherstellungscodes übrig');

	// Abmelden, Passwort – dann der Code aus der App
	await page.getByRole('button', { name: 'Abmelden' }).first().click();
	await expect(page).toHaveURL(/\/login$/);
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
	await page.getByLabel('Bestätigungscode').fill('000000');
	await page.getByRole('button', { name: 'Bestätigen' }).click();
	await expect(page.getByRole('alert')).toHaveText('Der Code ist falsch.');
	await page.getByLabel('Bestätigungscode').fill(totp(secret, 1));
	await page.getByRole('button', { name: 'Bestätigen' }).click();
	await expect(page).toHaveURL(/\/$/);

	// Mit einem Wiederherstellungscode wieder abschalten
	await page.goto('/settings');
	await section.getByLabel('Passwort zur Bestätigung').fill(PASSWORD);
	await section.getByLabel('Code aus der App oder Wiederherstellungscode').fill(recovery);
	await section.getByRole('button', { name: 'Zwei-Faktor abschalten' }).click();
	await expect(page.getByRole('status')).toContainText('Zwei-Faktor abgeschaltet');
	await expect(section).toContainText('Nicht eingerichtet.');

	expect(problems).toEqual([]);
});
