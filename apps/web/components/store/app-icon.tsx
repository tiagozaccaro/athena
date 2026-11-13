import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@workspace/ui/components/avatar"
import { cn } from "@workspace/ui/lib/utils"

/** A store app's icon, falling back to its initials when the image can't load. */
export function AppIcon({
  title,
  icon,
  className,
}: {
  title: string
  icon?: string | null
  className?: string
}) {
  const initials = title
    .split(/[\s-]+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
  return (
    <Avatar className={cn("size-10 rounded-lg after:rounded-lg", className)}>
      {icon ? (
        <AvatarImage
          src={icon}
          alt=""
          className="rounded-lg object-contain p-1"
        />
      ) : null}
      <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
    </Avatar>
  )
}
