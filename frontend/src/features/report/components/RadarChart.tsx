import { dimensionLabels, type ReportDimension } from "@/features/report/types";

export type RadarDatum = {
  dimension: ReportDimension;
  score: number | null;
};

const center = { x: 160, y: 132 };
const radius = 86;

const pointAt = (index: number, value: number) => {
  const angle = (Math.PI * 2 * index) / 4 - Math.PI / 2;
  return {
    x: center.x + Math.cos(angle) * radius * value,
    y: center.y + Math.sin(angle) * radius * value,
  };
};

const pointString = (points: readonly { x: number; y: number }[]) =>
  points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");

export default function RadarChart({ scores }: { scores: readonly RadarDatum[] }) {
  const complete = scores.length === 4 && scores.every((item) => item.score !== null);
  const dataPoints = complete
    ? scores.map((item, index) => pointAt(index, (item.score ?? 0) / 100))
    : [];
  const rings = [0.25, 0.5, 0.75, 1].map((scale) =>
    pointString([0, 1, 2, 3].map((index) => pointAt(index, scale))),
  );

  return (
    <section className="report-radar" aria-labelledby="report-radar-title">
      <div className="report-section-heading">
        <div>
          <p className="eyebrow">DIMENSIONS</p>
          <h2 id="report-radar-title">能力雷达</h2>
        </div>
        {!complete ? <span className="report-data-warning">评分维度数据异常</span> : null}
      </div>
      <div className="radar-layout">
        <svg className="radar-svg" viewBox="0 0 320 270" role="img" aria-label="面试能力雷达图">
          {rings.map((points, index) => (
            <polygon className="radar-ring" key={points} points={points} data-ring={index + 1} />
          ))}
          {[0, 1, 2, 3].map((index) => {
            const end = pointAt(index, 1);
            return <line className="radar-axis" key={index} x1={center.x} y1={center.y} x2={end.x} y2={end.y} />;
          })}
          {complete ? <polygon className="radar-value" points={pointString(dataPoints)} /> : null}
          {complete
            ? dataPoints.map((point, index) => <circle className="radar-point" key={index} cx={point.x} cy={point.y} r="4" />)
            : null}
          {scores.map((item, index) => {
            const labelPoint = pointAt(index, 1.22);
            return (
              <text className="radar-label" key={item.dimension} x={labelPoint.x} y={labelPoint.y} textAnchor="middle">
                {dimensionLabels[item.dimension]}
              </text>
            );
          })}
        </svg>
        <table className="radar-table">
          <caption>面试能力维度分数</caption>
          <tbody>
            {scores.map((item) => (
              <tr key={item.dimension}>
                <th scope="row">{dimensionLabels[item.dimension]}</th>
                <td>{item.score === null ? "数据异常" : `${item.score} / 100`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
