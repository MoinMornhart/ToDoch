import { expect, test } from '@playwright/test';

// Läuft nach app.spec.ts (Konto existiert).
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

function isoInDays(days: number): string {
	const date = new Date();
	date.setDate(date.getDate() + days);
	return date.toLocaleDateString('en-CA');
}

test('Telefontermin mit Entwurf, Kontaktvorschlag, Folgeaufgabe und ICS', async ({ page }) => {
	const problems: string[] = [];
	page.on('console', (m) => {
		if (/content security policy|refused to/i.test(m.text())) problems.push(m.text());
	});
	page.on('pageerror', (e) => problems.push(e.message));

	await page.goto('/login');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden' }).click();
	await expect(page).toHaveURL(/\/$/);

	// Kürzel „t“ öffnet das Formular
	await page.locator('main h1').click();
	await page.keyboard.press('t');
	const form = page.getByRole('dialog', { name: 'Telefontermin' });
	await expect(form).toBeVisible();
	await form.getByLabel('Name', { exact: true }).fill('Anna Berger');
	await form.getByLabel('Firma').fill('Berger GmbH');
	await form.getByLabel('Telefon', { exact: true }).fill('030 123456');
	await form.getByLabel('E-Mail').fill('anna@berger.example');

	// Entwurf übersteht das Neuladen
	await page.reload();
	await page.locator('main h1').click();
	await page.keyboard.press('t');
	await expect(form.getByText('Entwurf wiederhergestellt.')).toBeVisible();
	await expect(form.getByLabel('Name', { exact: true })).toHaveValue('Anna Berger');

	await form.getByLabel('Datum', { exact: true }).fill(isoInDays(3));
	await form.getByLabel('Uhrzeit').fill('10:00');
	await form.getByLabel('Dauer').selectOption({ label: '45 Min.' });
	await form.getByRole('button', { name: 'Vor Ort' }).click();
	await form.getByLabel('Adresse des Treffpunkts').fill('Hauptstraße 1, Berlin');
	await form.getByLabel('Gesprächspartner').fill('Frau Berger');
	await form.getByLabel('Notizen').fill('Vertrag mitbringen, **Aktenzeichen 4711**');
	await form.getByText('Folgeaufgabe anlegen').click();
	await form.getByLabel('Tage vorher').fill('1');
	await form.getByRole('button', { name: 'Speichern' }).click();

	await expect(form.getByText('Gespeichert: Termin mit Anna Berger (Berger GmbH)')).toBeVisible();
	await expect(form.getByText(/Folgeaufgabe „Unterlagen vorbereiten“/)).toBeVisible();
	const ics = form.getByRole('link', { name: 'ICS herunterladen' });
	const href = await ics.getAttribute('href');
	expect(href).toMatch(/^\/api\/events\/[\w-]+\/ics$/);
	const file = await page.request.get(href!);
	expect(await file.text()).toContain('LOCATION:Hauptstraße 1\\, Berlin');
	expect(await file.text()).not.toContain('Aktenzeichen');
	await expect(form.getByRole('link', { name: 'Per E-Mail senden' })).toHaveAttribute(
		'href',
		/^mailto:anna%40berger\.example\?subject=/
	);

	// Weiterer Termin für denselben Kontakt: Kontakt ist vorausgefüllt
	await form.getByRole('button', { name: 'Weiterer Termin für Anna Berger' }).click();
	await expect(form.getByLabel('Name', { exact: true })).toHaveValue('Anna Berger');
	await expect(form.getByLabel('Telefon', { exact: true })).toHaveValue('030 123456');
	await form.getByRole('button', { name: 'Abbrechen' }).click();
	await expect(form).toBeHidden();

	// Kontaktvorschlag beim Tippen
	await page.getByRole('button', { name: 'Telefontermin' }).click();
	await form.getByLabel('Name', { exact: true }).fill('');
	await form.getByLabel('Name', { exact: true }).pressSequentially('Ann');
	await form.getByRole('option', { name: /Anna Berger/ }).click();
	await expect(form.getByLabel('Firma')).toHaveValue('Berger GmbH');
	await form.getByRole('button', { name: 'Anderer Kontakt' }).click();
	await expect(form.getByLabel('Firma')).toHaveValue('');
	await form.getByRole('button', { name: 'Abbrechen' }).click();

	// Folgeaufgabe führt zum Termin, der Termin zeigt Kontakt und Aufgabe
	await page.getByRole('link', { name: 'Alle offen' }).first().click();
	await page.getByRole('button', { name: /^Unterlagen vorbereiten/ }).click();
	await page.getByRole('button', { name: 'Zum Termin' }).click();
	const event = page.getByRole('dialog', { name: 'Termin bearbeiten' });
	await expect(event.getByRole('link', { name: '030 123456' })).toHaveAttribute(
		'href',
		'tel:030 123456'
	);
	await expect(event.getByText(/Vereinbart per Telefon .* mit Frau Berger/)).toBeVisible();
	await expect(event.getByRole('button', { name: /Unterlagen vorbereiten/ })).toBeVisible();
	await page.keyboard.press('Escape');

	// Kontakte unter Einstellungen
	await page.getByRole('link', { name: 'Einstellungen' }).first().click();
	const contacts = page.getByRole('region', { name: 'Kontakte' });
	await expect(contacts).toContainText('Anna Berger');
	await expect(contacts).toContainText('1× verwendet');

	expect(problems).toEqual([]);
});
