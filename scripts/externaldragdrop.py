import hou
import os
import toolutils
import re
import json

def createMaterial(files, meta, cwd, path, pos, mattype):
    ms_principled = {'Albedo': 'basecolor', 'AO': 'occlusion', 'Specular': 'reflect', 'Displacement': 'dispTex', \
    'Normal': 'baseNormal', 'Bump': 'coatBump_bumpTexture', 'Roughness': 'rough', 'Transmission': 'transparency', 'Metalness': 'metallic', \
    'Opacity': 'opaccolor', 'Translucency': 'transcolor', 'Disp_scale': 'dispTex_scale', 'Tile': 'tiling'}

    ms_mtlx = {'Albedo': 'basecolor', 'AO': 'occlusion', 'Specular': 'specular', 'Displacement': 'displacement', \
    'Normal': 'normal', 'Bump': 'bump', 'Roughness': 'rough', 'Transmission': 'transmission', 'Metalness': 'metallic', \
    'Opacity': 'opacity', 'Translucency': 'transmission', 'Disp_scale': 'displacement_scale', 'Tile': 'tiling'}

    ms_types = {'Principled': ms_principled, 'Mtlx': ms_mtlx, 'Redshift': {}}
    shader_type = {'Principled': 'principledshader', 'Mtlx': 'np_mtlx', 'Redshift': ''}

    ms_args = ms_types[mattype]
    height = 1
    scan = (1,1)

    # create or find matnet
    if not (cwd.type().name() == 'matnet' or cwd.type().name() == 'materiallibrary'):
        matnets = [m for m in cwd.children() if m.type().name() == 'matnet']
        if len(matnets) > 0:
            matnet = matnets[0]
            hou.setPwd(matnet)
        else:
            matnet = cwd.createNode('matnet')
            hou.setPwd(matnet)
    else:
        matnet = cwd

    # get textures 
    jpgs = [f for f in files if f.endswith('.jpg')]
    exrs = [f for f in files if f.endswith('.exr')]
    
    # get metadata
    try:
        data = meta['meta']
        for val in data:
            if val['key'] == 'height':
                height = float(val['value'].split(' ')[0])
            if val['key'] == 'scanArea':
                area_str = val['value'][:3]
                scan = (float(area_str[0]), float(area_str[2]))
    except KeyError:
        pass

    # create shader
    shader = matnet.createNode(shader_type[mattype],os.path.basename(path))
    shader.setPosition(pos)
    pos = hou.Vector2(pos.x() + shader.size().x()*2, pos.y())

    # set metadata to parms
    shader.parm(ms_args['Disp_scale']).set(height)

    # if principled modify some defaults
    if mattype == 'Principled':
        shader.parmTuple('basecolor').set((1,1,1))
        shader.parm('dispTex_offset').set(0)


    #set textures
    for tex in jpgs+exrs:
        try:
            suffix = re.search(r'_([A-Z][a-zA-Z]*).', tex).group(1)
        except AttributeError:
            continue
        try:
            parmname = ms_args[suffix]

            # fill principled parameters
            if mattype == 'Principled':
                if suffix == 'Normal':
                    shader.parm('baseBumpAndNormal_enable').set(1)
                elif suffix == 'Displacement':
                    shader.parm('dispTex_enable').set(1)
                elif suffix == 'Bump':
                    shader.parm('separateCoatNormals').set(1)
                    shader.parm('coatBumpAndNormal_type').set('bump')
                    continue
                else:
                    shader.parm('{}_useTexture'.format(parmname)).set(1)
                shader.parm('{}_texture'.format(parmname)).set(os.path.abspath(tex))

            # fill mtlx parameters
            elif mattype == 'Mtlx':
                shader.parm('{}_file'.format(parmname)).set(os.path.abspath(tex))

        except KeyError:
            print('suffix {} does not exist'.format(suffix))

    return shader, pos


def dropAccept(file_list):
    if len(file_list) == 1 and os.path.splitext(file_list[0])[1] == ".hip":
        return False

    panetab = hou.ui.paneTabUnderCursor()
    if isinstance(panetab, hou.NetworkEditor):
        pos = panetab.cursorPosition()
        cwd = panetab.pwd()
        for i, path in enumerate(file_list):
            if os.path.isdir(path):
                os.chdir(path)
                files = os.listdir('.')
                meta = None
                for f in files:
                    if f.endswith('.json'):
                        with open(f, 'r') as js:
                            meta = json.loads(js.read())
                if meta is not None:
                    if 'surface' in meta['tags'] or 'surface' in meta['categories'] \
                    or 'decal' in meta['tags']:
                        types = ('Principled', 'Mtlx', 'Redshift')
                        if i == 0:
                            mode = hou.ui.displayMessage('Choose type', types)
                            mattype = types[mode]
                        shader ,pos = createMaterial(files, meta, cwd, path, pos, mattype)

    return True