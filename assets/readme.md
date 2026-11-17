# assets

*the icon in five backgrounds, for the places that draw it larger than a page*

the art here is the same cat-shaped speech bubble as `logo.png` at the root of the repo, with the
background colour swapped. `logo.png` is the copy the package ships and the one the readme points at,
at 256px, because a page draws it at 120px and 256 covers the densest screen worth measuring for.
these are the same drawing at 512px in five colours, for a card, a banner or a gallery, where one
small icon is not the whole picture.

| file | background at the corner | the same colour in from the edge | where it earns its place |
| --- | --- | --- | --- |
| `maroon.png` | `#972a51` | `#9b2b54` | the darkest of the five, and the one that reads as a lamp in a dim room |
| `yellow.png` | `#fde9aa` | `#fceab2` | the lightest, closest to paper: the glow almost disappears into it |
| `purple.png` | `#be9ff1` | `#caabf0` | the softest, and the nearest the shipped icon |
| `blue.png` | `#34a7fd` | `#40bcfd` | the coldest, the one that reads as a screen rather than a room |
| `green.png` | `#a6cc99` | `#a8cd9f` | the calmest, the least like a notification |

the background is not a flat fill, so a single hex is a lie in both directions: it is a lit room with
the subject glowing in it, and the two columns are the same room measured at its corner and just inside
the top edge. if you need the colour as a page background, sample it rather than trusting these, because
the gradient is the point.

## why 512 and not the original 1024

the source drawings are 1024px and about 1.3MB each, which is a megabyte of marketing artwork in a
package repo that audits itself for bytes. 512 is two pixels of source per pixel at a 256px placement,
which is the largest these are drawn outside a gallery, and every file is under 220KB. a bigger render
should come from the source art rather than from these, because upscaling a gradient shows.

## not shipped

`pypi/build.py` ships `logo.png` and this folder deliberately stays out of the wheel: an install never
draws a banner, and five 200KB pngs in every `pip install` is a tax on people who only want a phone
number. a test pins that, so adding these to the package has to be a decision rather than a drift.
