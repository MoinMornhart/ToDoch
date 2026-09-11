import type { DayLabels } from '$lib/dates';
import { t } from '$lib/i18n/index.svelte';
import type { RuleLabels } from '$lib/recurrence';

export function dayLabels(): DayLabels {
	return { today: t('date.today'), tomorrow: t('date.tomorrow'), yesterday: t('date.yesterday') };
}

export function ruleLabels(): RuleLabels {
	return {
		freq: {
			DAILY: t('rec.DAILY'),
			WEEKLY: t('rec.WEEKLY'),
			MONTHLY: t('rec.MONTHLY'),
			YEARLY: t('rec.YEARLY')
		},
		every: t('rec.every'),
		units: {
			DAILY: t('rec.unit.DAILY'),
			WEEKLY: t('rec.unit.WEEKLY'),
			MONTHLY: t('rec.unit.MONTHLY'),
			YEARLY: t('rec.unit.YEARLY')
		},
		until: t('rec.until')
	};
}

export const AREA_ICONS = [
	'circle',
	'briefcase',
	'home',
	'heart',
	'star',
	'book',
	'users',
	'cart',
	'car',
	'dumbbell',
	'music',
	'leaf',
	'code',
	'wallet',
	'plane',
	'school'
] as const;
