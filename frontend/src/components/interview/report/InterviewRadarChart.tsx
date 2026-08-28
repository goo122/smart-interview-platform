import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { RadarPoint } from "@/components/interview/report/types";

type InterviewRadarChartProps = {
  points: RadarPoint[];
};

export default function InterviewRadarChart({
  points,
}: InterviewRadarChartProps) {
  const [hovered, setHovered] = useState<{
    label: string;
    value: number;
    x: number;
    y: number;
  } | null>(null);

  if (points.length === 0) {
    return (
      <div className="mx-auto flex h-[260px] w-[260px] items-center justify-center rounded-xl border border-dashed border-slate-200 text-xs text-slate-400">
        暂无雷达数据
      </div>
    );
  }

  const size = 260;
  const center = size / 2;
  const radius = 96;
  const levels = [0.25, 0.5, 0.75, 1];
  const pointsOnChart = points.map((item, index) => {
    const angle = (Math.PI * 2 * index) / points.length - Math.PI / 2;
    const r = (item.value / 100) * radius;
    return [center + Math.cos(angle) * r, center + Math.sin(angle) * r];
  });
  const polygon = pointsOnChart.map((point) => point.join(",")).join(" ");
  const labelRadius = radius + 30;
  const hoverPoints = points.map((item, index) => {
    const angle = (Math.PI * 2 * index) / points.length - Math.PI / 2;
    const r = (item.value / 100) * radius;
    return {
      ...item,
      x: center + Math.cos(angle) * r,
      y: center + Math.sin(angle) * r,
      labelX: center + Math.cos(angle) * labelRadius,
      labelY: center + Math.sin(angle) * labelRadius,
    };
  });

  return (
    <div className="relative w-fit mx-auto">
      <motion.svg
        width={size}
        height={size}
        className="mx-auto"
        onMouseLeave={() => setHovered(null)}
        initial={{ opacity: 0, scale: 0.94, filter: "blur(3px)" }}
        animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      >
        {levels.map((level) => (
          <polygon
            key={level}
            points={points
              .map((_, index) => {
                const angle =
                  (Math.PI * 2 * index) / points.length - Math.PI / 2;
                const r = radius * level;
                return [
                  center + Math.cos(angle) * r,
                  center + Math.sin(angle) * r,
                ].join(",");
              })
              .join(" ")}
            fill="none"
            stroke="#e2e8f0"
          />
        ))}
        <motion.polygon
          points={polygon}
          fill="#6366f1"
          fillOpacity={hovered ? "0.28" : "0.18"}
          stroke="#6366f1"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.35, delay: 0.08, ease: "easeOut" }}
        />
        {hoverPoints.map((item) => (
          <g key={item.label}>
            <motion.circle
              cx={item.x}
              cy={item.y}
              r={5}
              fill="#6366f1"
              opacity={hovered?.label === item.label ? 0.9 : 0.6}
              initial={{ opacity: 0, scale: 0.2 }}
              animate={{
                opacity: hovered?.label === item.label ? 0.9 : 0.6,
                scale: 1,
              }}
              transition={{ duration: 0.25, ease: "easeOut" }}
            />
            <circle
              cx={item.x}
              cy={item.y}
              r={12}
              fill="transparent"
              onMouseEnter={() =>
                setHovered({
                  label: item.label,
                  value: item.value,
                  x: item.x,
                  y: item.y,
                })
              }
              onMouseMove={() =>
                setHovered({
                  label: item.label,
                  value: item.value,
                  x: item.x,
                  y: item.y,
                })
              }
            />
          </g>
        ))}
        {hoverPoints.map((item) => (
          <text
            key={item.label}
            x={item.labelX}
            y={item.labelY}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="12"
            fill="#64748b"
          >
            {item.label}
          </text>
        ))}
      </motion.svg>
      <AnimatePresence>
        {hovered ? (
          <motion.div
            className="absolute -translate-x-1/2 -translate-y-full rounded-lg border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 shadow-sm"
            style={{ left: hovered.x, top: hovered.y - 10 }}
            initial={{ opacity: 0, y: 6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.96 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            {hovered.label}：{hovered.value}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
