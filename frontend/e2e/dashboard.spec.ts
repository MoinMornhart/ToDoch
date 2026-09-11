import { expect, test } from '@playwright/test';

// Läuft nach app.spec.ts und calendar.spec.ts (Konto und Beispieldaten existieren).
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

test('Übersicht als Startseite, Aufgabe als Ticket, gekürzter Kalender', async ({ page }) => {
	const problems: string[] = [];
	page.on('console', (m) => {
		if (/content security policy|refused to/i.test(m.text())) problems.push(m.text());
	});
	page.on('pageerror', (e) => problems.push(e.message));

	await page.goto('/login');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden' }).click();

	// Übersicht
	await expect(page).toHaveURL(/\/$/);
	await expect(page.getByRole('heading', { level: 1 })).toContainText('Admin');
	await expect(page.getByRole('region', { name: 'Heute' })).toContainText('Wäsche abhängen');

	// Neue Aufgabe als Ticket über das Menü „Neu“
	await page.getByRole('button', { name: 'Neu', exact: true }).first().click();
	await page.getByRole('menuitem', { name: /Aufgabe/ }).click();
	const ticket = page.getByRole('dialog', { name: 'Aufgabe anlegen' });
	await ticket.getByLabel('Titel').fill('Vertrag prüfen');
	await ticket.getByText('Hoch', { exact: true }).click();
	await ticket.getByLabel('Unterpunkt hinzufügen').first().fill('Klauseln lesen');
	await ticket.getByLabel('Notiz').fill('Frist beachten');
	await ticket.getByRole('button', { name: 'Speichern' }).click();
	await expect(ticket).toBeHidden();
	await page.getByRole('link', { name: 'Alle offen' }).first().click();
	await expect(page.getByRole('button', { name: /^Vertrag prüfen/ })).toContainText('0/1');

	// Kalender für „Arbeit“ auf Mo–Fr, 8–18 Uhr kürzen
	await page.getByRole('link', { name: 'Bereiche' }).first().click();
	const days = page.getByRole('group', { name: 'Kalendertage für Arbeit' });
	await days.getByRole('button', { name: 'Sa' }).click();
	await expect(days.getByRole('button', { name: 'Sa' })).toHaveAttribute('aria-pressed', 'false');
	await days.getByRole('button', { name: 'So' }).click();
	await expect(days.getByRole('button', { name: 'So' })).toHaveAttribute('aria-pressed', 'false');
	await page.getByLabel('Bereich wählen').selectOption({ label: 'Arbeit' });
	await page.getByRole('link', { name: 'Kalender' }).first().click();
	await page.getByRole('button', { name: 'Woche' }).click();
	await expect(page.getByRole('button', { name: /Samstag/ })).toHaveCount(0);
	await expect(page.getByRole('button', { name: /Montag/ })).toHaveCount(1);
	await page.getByLabel('Bereich wählen').selectOption({ label: 'Alle Bereiche' });
	await expect(page.getByRole('button', { name: /Samstag/ })).toHaveCount(1);

	// Dunkles Design: Umschalter im Kopf, Auswahl bleibt nach dem Neuladen
	const html = page.locator('html');
	await expect(html).toHaveAttribute('data-theme', 'light');
	await page.getByRole('button', { name: 'Dunkles Design einschalten' }).click();
	await expect(html).toHaveAttribute('data-theme', 'dark');
	await page.reload();
	await expect(html).toHaveAttribute('data-theme', 'dark');
	await page.getByRole('link', { name: 'Einstellungen' }).first().click();
	await page.getByRole('button', { name: 'System' }).click();
	await expect(html).toHaveAttribute('data-theme', 'light');

	expect(problems).toEqual([]);
});
