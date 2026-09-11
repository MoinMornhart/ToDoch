import { expect, test, type Page } from '@playwright/test';

const CODE = 'e2e-setup-code-123456';
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

test.describe.configure({ mode: 'serial' });

/** Sammelt CSP-Verstöße und Laufzeitfehler – beides darf nie auftreten. */
function watchProblems(page: Page): string[] {
	const problems: string[] = [];
	page.on('console', (message) => {
		if (/content security policy|refused to/i.test(message.text())) problems.push(message.text());
	});
	page.on('pageerror', (error) => problems.push(`pageerror: ${error.message}`));
	return problems;
}

async function blurInputs(page: Page) {
	await page.locator('main h1').click();
}

test('Einrichtung, Schnellerfassung, Tastatur, Bearbeiten und Suche', async ({ page }) => {
	const problems = watchProblems(page);

	await page.goto('/');
	await expect(page).toHaveURL(/\/setup$/);
	await page.goto(`/setup#code=${CODE}`);
	await expect(page.getByLabel('Einrichtungscode')).toHaveValue(CODE);
	await page.getByLabel('Dein Name').fill('Admin');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort', { exact: true }).fill(PASSWORD);
	await page.getByLabel('Passwort wiederholen').fill(PASSWORD);
	await page.getByRole('button', { name: 'Einrichten' }).click();

	await expect(page).toHaveURL(/\/$/);
	await page.goto('/today');
	await expect(page.getByText(/Nichts fällig/)).toBeVisible();

	const quick = page.getByLabel('Neue Aufgabe');
	await quick.fill('Wäsche aufhängen heute !hoch #haushalt');
	await expect(page.getByTestId('quick-preview')).toContainText('haushalt');
	await expect(page.getByTestId('quick-preview')).toContainText('Hoch');
	await quick.press('Enter');
	await expect(page.getByRole('button', { name: /^Wäsche aufhängen/ })).toBeVisible();

	await quick.fill('Steuer abgeben morgen 9:00');
	await quick.press('Enter');
	await expect(page.getByRole('status')).toContainText('Aufgabe angelegt');
	await expect(page.getByRole('button', { name: /^Steuer abgeben/ })).toHaveCount(0);

	await page.getByRole('link', { name: 'Demnächst' }).first().click();
	await expect(page.getByRole('button', { name: /^Steuer abgeben/ })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Morgen' })).toBeVisible();

	// Tastatur: j wählt die erste Aufgabe, x hakt sie ab, Rückgängig stellt sie wieder her.
	await page.getByRole('link', { name: 'Heute' }).first().click();
	await expect(page.getByRole('button', { name: /^Wäsche aufhängen/ })).toBeVisible();
	await blurInputs(page);
	await page.keyboard.press('j');
	await expect(page.getByRole('button', { name: /^Wäsche aufhängen/ })).toBeFocused();
	await page.keyboard.press('x');
	await expect(page.getByText(/Nichts fällig/)).toBeVisible();
	await page.getByRole('button', { name: 'Rückgängig' }).click();
	await expect(page.getByRole('button', { name: /^Wäsche aufhängen/ })).toBeVisible();

	// Bearbeiten-Dialog
	await page.getByRole('button', { name: /^Wäsche aufhängen/ }).click();
	const dialog = page.getByRole('dialog', { name: 'Aufgabe bearbeiten' });
	await expect(dialog).toBeVisible();
	await dialog.getByLabel('Titel').fill('Wäsche abhängen');
	await dialog.getByLabel('Unterpunkt hinzufügen').first().fill('Socken sortieren');
	await dialog.getByRole('button', { name: 'Speichern' }).click();
	await expect(dialog).toBeHidden();
	await expect(page.getByRole('button', { name: /^Wäsche abhängen/ })).toContainText('0/1');

	// Suche per „/“
	await blurInputs(page);
	await page.keyboard.press('/');
	const search = page.getByRole('combobox', { name: 'Suchen' });
	await search.fill('steuer');
	await expect(page.getByRole('option', { name: /Steuer abgeben/ })).toBeVisible();
	await search.press('Enter');
	await expect(page.getByRole('dialog', { name: 'Aufgabe bearbeiten' })).toBeVisible();
	await expect(page.getByLabel('Titel')).toHaveValue('Steuer abgeben');
	await page.keyboard.press('Escape');

	// Hilfe per „?“
	await blurInputs(page);
	await page.keyboard.press('?');
	await expect(page.getByRole('dialog', { name: 'Tastaturkürzel' })).toBeVisible();
	await page.keyboard.press('Escape');

	expect(problems).toEqual([]);
});

test('Bereiche filtern alle Ansichten', async ({ page }) => {
	const problems = watchProblems(page);
	await page.goto('/login');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden' }).click();
	await expect(page).toHaveURL(/\/$/);
	await page.goto('/today');

	const quick = page.getByLabel('Neue Aufgabe');
	await quick.fill('Angebot schreiben heute @arbeit');
	await quick.press('Enter');
	await expect(page.getByRole('button', { name: /^Angebot schreiben/ })).toBeVisible();
	await quick.fill('Einkaufen heute @privat');
	await quick.press('Enter');
	await expect(page.getByRole('button', { name: /^Einkaufen/ })).toBeVisible();

	await page.getByLabel('Bereich wählen').selectOption({ label: 'Privat' });
	await expect(page.getByRole('button', { name: /^Angebot schreiben/ })).toHaveCount(0);
	await expect(page.getByRole('button', { name: /^Einkaufen/ })).toBeVisible();

	await page.getByLabel('Bereich wählen').selectOption({ label: 'Arbeit' });
	await expect(page.getByRole('button', { name: /^Angebot schreiben/ })).toBeVisible();
	await expect(page.getByRole('button', { name: /^Einkaufen/ })).toHaveCount(0);

	await page.getByLabel('Bereich wählen').selectOption({ label: 'Alle Bereiche' });
	expect(problems).toEqual([]);
});

test('Abmelden, falsches Passwort, erneut anmelden', async ({ page }) => {
	await page.goto('/login');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill('falsches-passwort');
	await page.getByRole('button', { name: 'Anmelden' }).click();
	await expect(page.getByRole('alert')).toHaveText('E-Mail-Adresse oder Passwort ist falsch.');

	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden' }).click();
	await expect(page).toHaveURL(/\/$/);
	await page.goto('/today');

	await page.getByRole('link', { name: 'Einstellungen' }).first().click();
	await expect(page.getByText('Dieses Gerät')).toBeVisible();
	await page.getByRole('button', { name: 'Abmelden' }).first().click();
	await expect(page).toHaveURL(/\/login$/);

	await page.goto('/today');
	await expect(page).toHaveURL(/\/login$/);
});
