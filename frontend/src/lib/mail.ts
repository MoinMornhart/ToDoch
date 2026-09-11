/** E-Mail: Typen der API und Servervorschläge für bekannte Anbieter (ohne Netzabfrage). */

export type MailSecurity = 'ssl' | 'starttls';

export interface MailAccountInfo {
	id: string;
	name: string;
	email: string;
	host: string;
	port: number;
	security: MailSecurity;
	username: string;
	folder: string;
	refresh_minutes: number;
	enabled: boolean;
	message_count: number;
	unread_count: number;
	last_synced_at: string | null;
	last_success_at: string | null;
	last_error: string | null;
	created_at: string;
	/** „oauth2“: mit Google/Microsoft verbunden (ohne Passwort). */
	auth: 'password' | 'oauth2';
	provider: OAuthProvider | null;
}

export type OAuthProvider = 'google' | 'microsoft';
export type OAuthProviders = Record<OAuthProvider, boolean>;

export interface MailMessage {
	id: string;
	account_id: string;
	account_name: string;
	from_name: string;
	from_address: string;
	subject: string;
	sent_at: string | null;
	received_at: string;
	snippet: string;
	is_read: boolean;
	attachment_count: number;
	/** Aufgabe, die aus dieser Mail entstanden ist. */
	task_id: string | null;
	/** Erkannter Termin (Einladung oder Datum im Text), wartet auf Bestätigung. */
	suggestion: MailSuggestion | null;
	/** Termin, der aus dem Vorschlag entstanden ist. */
	event_id: string | null;
}

export interface MailSuggestion {
	source: 'invite' | 'text';
	title: string;
	location: string;
	all_day: boolean;
	start_date: string;
	start_time: string | null;
	/** Bei ganztägigen Terminen inklusiv. */
	end_date: string;
	end_time: string | null;
	status: 'pending' | 'accepted' | 'dismissed';
}

export interface MailMessageDetail extends MailMessage {
	message_id: string;
	recipients: string;
	/** Immer reiner Text – HTML-Mails werden auf dem Server umgewandelt. */
	body_text: string;
	has_html: boolean;
	truncated: boolean;
}

export interface MailRuleInfo {
	id: string;
	name: string;
	/** Leer = alle Postfächer. */
	account_id: string | null;
	account_name: string | null;
	from_contains: string;
	subject_contains: string;
	body_contains: string;
	create_task: boolean;
	mark_read: boolean;
	/** Leer = erster Bereich. */
	area_id: string | null;
	area_name: string | null;
	priority: number;
	tags: string[];
	enabled: boolean;
	match_count: number;
	last_matched_at: string | null;
	created_at: string;
}

export interface ImapGuess {
	host: string;
	port: number;
	security: MailSecurity;
	/** „app“: App-Passwort nötig, „oauth“: nur mit OAuth-Anmeldung (kommt mit Meilenstein 5). */
	hint: 'app' | 'oauth' | null;
	/** Aus der Liste bekannter Anbieter – sonst nur geraten (imap.<domain>). */
	known: boolean;
}

const PROVIDERS: [string[], string, ImapGuess['hint']][] = [
	[['gmail.com', 'googlemail.com'], 'imap.gmail.com', 'app'],
	[['icloud.com', 'me.com', 'mac.com'], 'imap.mail.me.com', 'app'],
	[['yahoo.com', 'yahoo.de', 'ymail.com'], 'imap.mail.yahoo.com', 'app'],
	[['aol.com', 'aol.de'], 'imap.aol.com', 'app'],
	[
		['outlook.com', 'outlook.de', 'hotmail.com', 'hotmail.de', 'live.com', 'live.de', 'msn.com'],
		'outlook.office365.com',
		'oauth'
	],
	[['gmx.de', 'gmx.net', 'gmx.at', 'gmx.ch', 'gmx.com'], 'imap.gmx.net', null],
	[['web.de'], 'imap.web.de', null],
	[['t-online.de', 'magenta.de'], 'secureimap.t-online.de', null],
	[['posteo.de', 'posteo.net', 'posteo.org'], 'posteo.de', null],
	[['mailbox.org'], 'imap.mailbox.org', null],
	[['freenet.de'], 'mx.freenet.de', null],
	[['ionos.de', 'online.de', '1und1.de'], 'imap.ionos.de', null]
];

export function guessImap(address: string): ImapGuess | null {
	const [local, domain] = address.trim().toLowerCase().split('@');
	if (!local || !domain || !domain.includes('.')) return null;
	for (const [domains, host, hint] of PROVIDERS) {
		if (domains.includes(domain)) return { host, port: 993, security: 'ssl', hint, known: true };
	}
	return { host: `imap.${domain}`, port: 993, security: 'ssl', hint: null, known: false };
}
