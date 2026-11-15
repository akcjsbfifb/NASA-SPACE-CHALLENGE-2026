type SearchVariableHeaderProps = {
	label: string;
	included: boolean;
	includeAriaLabel: string;
	disabled?: boolean;
	onIncludedChange: (included: boolean) => void;
};

export default function SearchVariableHeader({
	label,
	included,
	includeAriaLabel,
	disabled,
	onIncludedChange,
}: SearchVariableHeaderProps) {
	return (
		<span className="field-header">
			<span>{label}</span>
			<input
				type="checkbox"
				role="switch"
				className="var-switch"
				checked={included}
				disabled={disabled}
				aria-label={includeAriaLabel}
				onChange={(event) => onIncludedChange(event.target.checked)}
			/>
		</span>
	);
}