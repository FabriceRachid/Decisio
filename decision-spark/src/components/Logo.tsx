interface LogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  className?: string;
}

const sizeMap = {
  sm: { img: "h-7 w-7", text: "text-lg" },
  md: { img: "h-9 w-9", text: "text-xl" },
  lg: { img: "h-14 w-14", text: "text-2xl" },
};

export function Logo({ size = "md", showText = true, className = "" }: LogoProps) {
  const s = sizeMap[size];
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <img src="/logo.png" alt="DecisioBI" className={`${s.img} rounded-xl object-contain`} />
      {showText && (
        <span className={`font-display ${s.text} font-semibold`}>
          Decisio<span className="text-gold">BI</span>
        </span>
      )}
    </div>
  );
}
