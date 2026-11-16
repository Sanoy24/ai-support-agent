import { Globe, Send, type LucideIcon } from "lucide-react";

const CHANNELS: Record<string, { label: string; icon: LucideIcon }> = {
  web: { label: "Website", icon: Globe },
  telegram: { label: "Telegram", icon: Send },
};

export function ChannelBadge({ channel }: { channel: string }) {
  const { label, icon: Icon } = CHANNELS[channel] ?? { label: channel, icon: Globe };
  return (
    <span className="inline-flex items-center gap-1 text-xs text-zinc-500">
      <Icon className="size-3.5" aria-hidden />
      {label}
    </span>
  );
}
