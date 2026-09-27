import hashlib

def generate_avatar_svg(email: str) -> str:
    # Deterministic hash based on email
    h = hashlib.md5(email.strip().lower().encode('utf-8')).hexdigest()
    
    # Extract values from hash
    # Colors
    hues = [int(h[i:i+3], 16) % 360 for i in range(0, 9, 3)]
    
    colors = [f"hsl({hues[0]}, 70%, 60%)", f"hsl({hues[1]}, 80%, 50%)", f"hsl({hues[2]}, 90%, 70%)"]
    bg_color = f"hsl({(hues[0] + 180) % 360}, 30%, 90%)"
    
    # Shapes: 0=circle, 1=rect, 2=polygon
    shape_types = [int(h[i], 16) % 3 for i in range(9, 12)]
    
    # Positions and sizes
    cx = [int(h[i:i+2], 16) % 60 + 20 for i in range(12, 18, 2)]
    cy = [int(h[i:i+2], 16) % 60 + 20 for i in range(18, 24, 2)]
    sizes = [int(h[i:i+2], 16) % 30 + 15 for i in range(24, 30, 2)]
    
    svg_elements = []
    
    for i in range(3):
        color = colors[i]
        x, y, s = cx[i], cy[i], sizes[i]
        
        if shape_types[i] == 0:
            svg_elements.append(f'<circle cx="{x}%" cy="{y}%" r="{s}%" fill="{color}" opacity="0.8" />')
        elif shape_types[i] == 1:
            svg_elements.append(f'<rect x="{x-s}%" y="{y-s}%" width="{s*2}%" height="{s*2}%" rx="10%" fill="{color}" opacity="0.8" transform="rotate({x*y % 360}, {x}, {y})" />')
        else:
            # Triangle
            x1, y1 = x, y - s
            x2, y2 = x - s, y + s
            x3, y3 = x + s, y + s
            svg_elements.append(f'<polygon points="{x1},{y1} {x2},{y2} {x3},{y3}" fill="{color}" opacity="0.8" transform="rotate({x*y % 360}, {x}, {y})" />')

    shapes_str = "\n  ".join(svg_elements)
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
  <rect width="100" height="100" fill="{bg_color}" />
  {shapes_str}
</svg>'''
    
    return svg
