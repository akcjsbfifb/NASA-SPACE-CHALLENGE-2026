export type SearchWeightRow = {
	id: string;
	name: string;
	weight: number;
	disabled?: boolean;
	onWeightChange: (value: number) => void;
};

type SearchWeightGroupProps = {
	weightLabel: string;
	rows: SearchWeightRow[];
};

export default function SearchWeightGroup({ weightLabel, rows }: SearchWeightGroupProps) {
	return (
		<div className="weight-group">
			<span className="weight-label">{weightLabel}</span>
			{rows.map((row) => (
				<label className="weight-row" key={row.id}>
					<span className="weight-name">{row.name}</span>
					<input
						type="range"
						min={0}
						max={1}
						step={0.1}
						disabled={row.disabled}
						value={row.weight}
						aria-valuetext={row.weight.toFixed(1)}
						onChange={(event) => row.onWeightChange(Number(event.target.value))}
					/>
				</label>
			))}
		</div>
	);
}