<script lang="ts">
	import {
		BookOpen,
		Briefcase,
		Car,
		Circle,
		Code,
		Dumbbell,
		GraduationCap,
		Heart,
		House,
		Leaf,
		Music,
		Plane,
		ShoppingCart,
		Star,
		Users,
		Wallet
	} from '@lucide/svelte';

	let {
		name,
		size = 16,
		class: className = ''
	}: { name: string; size?: number; class?: string } = $props();

	const icons: Record<string, typeof Circle> = {
		circle: Circle,
		briefcase: Briefcase,
		home: House,
		heart: Heart,
		star: Star,
		book: BookOpen,
		users: Users,
		cart: ShoppingCart,
		car: Car,
		dumbbell: Dumbbell,
		music: Music,
		leaf: Leaf,
		code: Code,
		wallet: Wallet,
		plane: Plane,
		school: GraduationCap
	};

	const Icon = $derived(icons[name] ?? Circle);
</script>

<Icon {size} class={className} aria-hidden="true" />
