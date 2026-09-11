import { expect, test } from '@playwright/test';

// Läuft nach app.spec.ts (Konto existiert). Stellt am Ende wieder auf Deutsch zurück.
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

test('Englisch: Anmeldeseite, Oberfläche und Fehlermeldungen des Servers', async ({ page }) => {
	const problems: string[] = [];
	page.on('pageerror', (e) => problems.push(e.message));

	// Sprache schon vor der Anmeldung umschalten – bleibt beim Neuladen erhalten
	await page.goto('/login');
	await page.getByRole('button', { name: 'English' }).click();
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sign in');
	await page.reload();
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sign in');
	await expect(page.locator('html')).toHaveAttribute('lang', 'en');

	// Fehlermeldung des Servers auf Englisch
	await page.getByLabel('Email address').fill(EMAIL);
	await page.getByLabel('Password').fill('wrong-password-123');
	await page.getByRole('button', { name: 'Sign in', exact: true }).click();
	await expect(page.getByRole('alert')).toHaveText('Email address or password is incorrect.');

	// Nach der Anmeldung gilt die Sprache aus dem Profil (hier Deutsch) …
	await page.getByLabel('Password').fill(PASSWORD);
	await page.getByRole('button', { name: 'Sign in', exact: true }).click();
	await expect(page).toHaveURL(/\/$/);
	await expect(page.getByRole('link', { name: 'Heute' }).first()).toBeVisible();

	// … und lässt sich dort dauerhaft auf Englisch stellen
	await page.getByRole('link', { name: 'Einstellungen' }).first().click();
	await page.getByLabel('Sprache').selectOption('en');
	await page.getByRole('button', { name: 'Profil speichern' }).click();
	await expect(page.getByRole('link', { name: 'Today' }).first()).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

	// Server-Fehler im Profil-Englisch
	await page.getByLabel('New password').fill('aaaaaaaaaaaa');
	await page.getByRole('button', { name: 'Change password' }).click();
	await expect(page.getByRole('status')).toContainText('The password is too simple.');

	// Zurück auf Deutsch für die folgenden Tests
	await page.getByLabel('Language').selectOption('de');
	await page.getByRole('button', { name: 'Save profile' }).click();
	await expect(page.getByRole('link', { name: 'Heute' }).first()).toBeVisible();
	await page.getByRole('button', { name: 'Abmelden' }).first().click();
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Anmelden');

	expect(problems).toEqual([]);
});
