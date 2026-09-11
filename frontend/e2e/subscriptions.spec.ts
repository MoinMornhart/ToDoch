import { expect, test } from '@playwright/test';

// Läuft nach app.spec.ts (Konto existiert). Echte Abrufe gibt es im Test nicht – geprüft wird,
// dass das Formular da ist und interne Adressen (SSRF) abgelehnt werden.
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

test('Kalender einbinden: Formular und Schutz vor internen Adressen', async ({ page }) => {
	const problems: string[] = [];
	page.on('pageerror', (e) => problems.push(e.message));

	await page.goto('/login');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
	await expect(page).toHaveURL(/\/$/);

	await page.getByRole('link', { name: 'Bereiche' }).first().click();
	const section = page.getByRole('region', { name: 'Kalender einbinden (ICS)' });
	await expect(section).toContainText('Streamo × ToDoch');
	await expect(section.getByText('Noch keine eingebundenen Kalender.')).toBeVisible();

	await section.getByLabel('Name', { exact: true }).fill('Streamo');
	await section.getByLabel(/Abo-Adresse/).fill('http://127.0.0.1:3000/api/public/calendar/x.ics');
	await section.getByRole('button', { name: 'Einbinden' }).click();
	await expect(page.getByRole('status')).toContainText('Diese Adresse ist nicht erlaubt.');
	await expect(section.getByText('Noch keine eingebundenen Kalender.')).toBeVisible();

	expect(problems).toEqual([]);
});
