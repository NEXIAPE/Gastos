import { groupedCategories, useCategories } from "../lib/categories";

/**
 * <select> de categorías, agrupadas por Tipo de Gasto (Fijo/Necesario/...)
 * con <optgroup> — mucho más fácil de escanear que una lista plana de 30+
 * categorías. Se usa en todos los lugares donde se elige una categoría.
 */
export default function CategorySelect({
  value, onChange, emptyLabel, style, id,
}: {
  value: string;
  onChange: (value: string) => void;
  /** Si se da, agrega una primera opción vacía con este texto (ej. "Todas"). */
  emptyLabel?: string;
  style?: React.CSSProperties;
  id?: string;
}) {
  const { categories } = useCategories();
  const groups = groupedCategories(categories);

  return (
    <select id={id} value={value} style={style} onChange={(e) => onChange(e.target.value)}>
      {emptyLabel !== undefined && <option value="">{emptyLabel}</option>}
      {groups.map(({ group, names }) => (
        <optgroup key={group} label={group}>
          {names.map((name) => <option key={name} value={name}>{name}</option>)}
        </optgroup>
      ))}
    </select>
  );
}
