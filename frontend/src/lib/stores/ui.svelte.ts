/** Globaler UI-Zustand: Dialoge, Fokus-Signale, Änderungszähler. */

class Ui {
	searchOpen = $state(false);
	helpOpen = $state(false);
	editTaskId = $state<string | null>(null);
	/** Die Schnellerfassung soll beim nächsten Anzeigen den Fokus bekommen. */
	quickAddPending = $state(false);
	quickAddMounted = $state(false);
	/** Wird nach jeder Änderung an Aufgaben erhöht – Listen laden dann neu. */
	version = $state(0);

	get dialogOpen(): boolean {
		return this.searchOpen || this.helpOpen || this.editTaskId !== null;
	}

	changed(): void {
		this.version++;
	}
}

export const ui = new Ui();
