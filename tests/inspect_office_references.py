"""Extract review-only contact sheets from video paths supplied on the command line."""
import argparse
from pathlib import Path
import av
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('videos', nargs='+', type=Path, help='vídeos para inspecionar')
parser.add_argument('--output', type=Path, default=Path('logs/office_references'))
args = parser.parse_args()
out=args.output;out.mkdir(parents=True,exist_ok=True)
for number,path in enumerate(args.videos,1):
    with av.open(str(path)) as video:
        stream=video.streams.video[0]
        duration=float(stream.duration*stream.time_base) if stream.duration else video.duration/av.time_base
        print(number, 'duration',duration,'size',stream.width,stream.height,'fps',stream.average_rate,flush=True)
        times=[duration*(.03+i*.115) for i in range(9)]
        sheet=Image.new('RGB',(960,1350),'#191922');draw=ImageDraw.Draw(sheet)
        for i,seconds in enumerate(times):
            video.seek(int(seconds/stream.time_base),stream=stream)
            for frame in video.decode(stream):
                if frame.time is None or frame.time>=seconds:
                    im=frame.to_image()
                    im.save(out/f'video{number}_{i}.jpg')
                    im.thumbnail((316,418))
                    x=(i%3)*320;y=(i//3)*450
                    sheet.paste(im,(x+(320-im.width)//2,y+24))
                    draw.text((x+8,y+5),f'Video {number} - {seconds:.1f}s',fill='white')
                    break
        sheet.save(out/f'video{number}_sheet.jpg')
