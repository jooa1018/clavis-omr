// Offline W2 SVG raster adapter. Sharp is a development tool, never a runtime dependency.
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const sharp = require(process.argv[4]);
sharp.concurrency(1);
(async () => {
  const root=process.argv[2], out=process.argv[3];
  fs.mkdirSync(out,{recursive:true});
  const records=[];
  // Fixed before measurement: four score variants, all three registered music fonts.
  for(let i=0;i<4;i++) for(const font of ['Leipzig','Bravura','Leland']) {
    const name=`train-smoke-${i}-${font}`;
    const svg=zlib.gunzipSync(fs.readFileSync(path.join(root,name,'page-1.svg.gz')));
    const target=path.join(out,name+'.png');
    const info=await sharp(svg,{density:144}).flatten({background:'white'}).greyscale().png().toFile(target);
    // prepare_smoke emits a paired SVG with only the explicit staff paths removed.
    const symbols=path.join(out,name+'-symbols.svg');
    if (!fs.existsSync(symbols)) throw new Error('Run prepare_smoke before rasterization');
    await sharp(symbols,{density:144}).flatten({background:'white'}).greyscale().png()
      .toFile(path.join(out,name+'-symbols.png'));
    records.push({name,width:info.width,height:info.height});
  }
  fs.writeFileSync(path.join(out,'rasters.json'),JSON.stringify({tool:'sharp',versions:sharp.versions,records},null,2)+'\n');
})().catch(e=>{console.error(e);process.exitCode=1;});
