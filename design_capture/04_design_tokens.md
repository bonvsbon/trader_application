# 04 · Design Tokens

Source of truth: `frontend/src/style.css` (`:root` = light, `[data-theme="dark"]`).
สีเป็น **OKLCH** ทั้งหมด. ค่าด้านล่างคัดมาตรง ๆ เพื่อใช้อ้างอิงตอน redesign.
(ถ้าเปลี่ยนธีม แก้ที่นี่ทีเดียว ทุกหน้าตามทันที — อย่า hardcode สีในหน้า)

## Color — Light (`:root`)
| Token | ค่า | ใช้ทำอะไร |
|---|---|---|
| `--bg` | `oklch(0.985 0.004 255)` | พื้นหลังแอป |
| `--surface` | `oklch(1 0 0)` | พื้น panel |
| `--surface-2` | `oklch(0.972 0.006 255)` | sidebar, input, hover |
| `--surface-3` | `oklch(0.955 0.008 255)` | hover เข้มขึ้น |
| `--ink` | `oklch(0.27 0.02 260)` | ตัวอักษรหลัก |
| `--ink-muted` | `oklch(0.49 0.02 260)` | ตัวอักษรรอง |
| `--ink-faint` | `oklch(0.52 0.018 260)` | label จาง/section label |
| `--border` | `oklch(0.91 0.008 260)` | เส้นขอบ |
| `--border-strong` | `oklch(0.84 0.01 260)` | ขอบ input |
| `--accent` | `oklch(0.55 0.15 255)` | แบรนด์/ปุ่มหลัก/active (น้ำเงิน) |
| `--accent-hover` | `oklch(0.50 0.16 255)` | hover ปุ่มหลัก |
| `--accent-ink` | `oklch(0.46 0.16 255)` | ลิงก์/active text |
| `--danger` | `oklch(0.53 0.20 27)` | ปุ่มอันตราย (แดง) |

### Semantic fg/bg (AA, hue เดียวกัน)
| สถานะ | fg | bg |
|---|---|---|
| allow (เขียว) | `--allow-fg` `oklch(0.44 0.13 150)` | `--allow-bg` `oklch(0.95 0.045 150)` |
| warn (เหลือง) | `--warn-fg` `oklch(0.48 0.10 70)` | `--warn-bg` `oklch(0.95 0.06 82)` |
| block (แดง) | `--block-fg` `oklch(0.49 0.18 27)` | `--block-bg` `oklch(0.95 0.05 27)` |
| neutral | `--neutral-fg` = ink-muted | `--neutral-bg` `oklch(0.95 0.006 260)` |

### Directional P&L
`--pos` `oklch(0.48 0.13 150)` (เขียว) · `--neg` `oklch(0.52 0.19 27)` (แดง)

## Color — Dark (`[data-theme="dark"]`) — ค่าที่ override
| Token | ค่า |
|---|---|
| `--bg` | `oklch(0.19 0.018 260)` |
| `--surface` | `oklch(0.235 0.02 260)` |
| `--surface-2` | `oklch(0.215 0.02 260)` |
| `--ink` | `oklch(0.96 0.008 260)` |
| `--accent` | `oklch(0.70 0.13 255)` |
| `--allow-fg/bg` | `oklch(0.82 0.14 150)` / `oklch(0.30 0.05 150)` |
| `--warn-fg/bg` | `oklch(0.84 0.12 82)` / `oklch(0.32 0.05 82)` |
| `--block-fg/bg` | `oklch(0.80 0.15 27)` / `oklch(0.33 0.06 27)` |
| `--pos/neg` | `oklch(0.80 0.14 150)` / `oklch(0.76 0.16 27)` |
(โครงเดียวกับ light แต่ปรับ lightness; ดูค่าครบใน style.css)

## Typography
- `--font-sans`: system-ui stack
- `--font-mono`: ui-monospace / Cascadia / SF Mono / JetBrains Mono — **ตัวเลขทุกที่
  ใช้ mono + tabular-nums**
- Scale: `--text-xs .75rem` · `sm .8125` · `base .875` · `md 1` · `lg 1.125` ·
  `xl 1.375` · `2xl 1.75`
- หัวข้อ: weight 650, letter-spacing −0.015em, text-wrap balance

## Spacing (4px base)
`--sp-1 2` `2 4` `3 6` `4 8` `5 12` `6 16` `7 20` `8 24` `9 32` `10 40` `12 48` (px)

## Radius
`--r-sm 6` · `--r-md 8` · `--r-lg 12` · `--r-pill 999`

## Shadow
`--shadow-sm` / `--shadow-md` / `--shadow-lg` (อ่อนใน light, ลึกใน dark)

## Motion
`--dur-fast 120ms` · `--dur 180ms` · `--dur-slow 240ms` ·
`--ease cubic-bezier(0.22, 1, 0.36, 1)`

## Layout constants
`--sidebar-w 244px` · `--content-max 1120px`
`z-index`: dropdown 100 · sticky 200 · backdrop 300 · modal 310 · toast 400 · tooltip 500

## คำแนะนำสำหรับ redesign
- แก้สี/spacing ที่ token แล้วทั้งแอปเปลี่ยนตาม — อย่าใส่ค่าดิบในแต่ละหน้า
- รักษา mapping **REAL=แดง / DEMO=เขียว** และ ALLOW/WARN/BLOCK ไว้ (เป็นภาษา safety)
- ตัวเลขเงิน/ราคา/R ใช้ mono tabular เสมอเพื่อให้ scan คอลัมน์ได้
- คุม contrast ระดับ AA (semantic pairs ออกแบบมาแล้ว) ทั้ง light/dark
