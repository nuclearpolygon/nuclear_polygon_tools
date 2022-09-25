import hou
import os
import toolutils
import re
import json

def createMaterial(files, meta, cwd, path, pos, mattype, use_meta=True):
    ms_principled = {'Albedo': 'basecolor', 'AO': 'occlusion', 'Specular': 'reflect', 'Displacement': 'dispTex', \
    'Normal': 'baseNormal', 'Bump': 'coatBump_bumpTexture', 'Roughness': 'rough', 'Transmission': 'transparency', 'Metalness': 'metallic', \
    'Opacity': 'opaccolor', 'Translucency': 'transcolor', 'Disp_scale': 'dispTex_scale', 'Tile': 'uvscale'}

    ms_mtlx = {'Albedo': 'basecolor', 'AO': 'occlusion', 'Specular': 'specular', 'Displacement': 'displacement', \
    'Normal': 'normal', 'Bump': 'bump', 'Roughness': 'rough', 'Transmission': 'transmission', 'Metalness': 'metallic', \
    'Opacity': 'opacity', 'Translucency': 'transmission', 'Disp_scale': 'displacement_scale', 'Tile': 'tiling'}

    ms_types = {'Principled': ms_principled, 'Mtlx': ms_mtlx, 'Redshift': {}}
    shader_type = {'Principled': 'principledshader', 'Mtlx': 'np_mtlx', 'Redshift': ''}

    ms_args = ms_types[mattype]
    height = 1
    scan = (1,1)

    # create or find matnet
    if cwd.type().name() == 'matnet' \
        or cwd.type().name() == 'materiallibrary' \
        or cwd.type().name() == 'mat' \
        or (cwd.type().name() == 'subnet' and cwd.parent().type().name() == 'materiallibrary'):
        matnet = cwd

    else:
        matnets = [m for m in cwd.children() if m.type().name() == 'matnet']
        if len(matnets) > 0:
            matnet = matnets[0]
            hou.setPwd(matnet)
        else:
            matnet = cwd.createNode('matnet')
            hou.setPwd(matnet)

    # get textures 
    jpgs = [f for f in files if f.endswith('.jpg')]
    exrs = [f for f in files if f.endswith('.exr')]
    
    # get metadata
    if use_meta:
        try:
            data = meta['meta']
            for val in data:
                if val['key'] == 'height':
                    height = float(val['value'].split(' ')[0])
                if val['key'] == 'scanArea':
                    area_str = val['value'].split(' ')[0].split('x')
                    scan = (float(area_str[0]), float(area_str[1]))
        except KeyError:
            pass
    else:
        height = .01
        scan = (1.0, 1.0)

    # create shader
    shader = matnet.createNode(shader_type[mattype],os.path.basename(path))
    shader.setPosition(pos)
    pos = hou.Vector2(pos.x() + shader.size().x()*2, pos.y())

    # set metadata to parms
    shader.parm(ms_args['Disp_scale']).set(height)
    shader.parmTuple(ms_args['Tile']).set(scan)

    # if principled modify some defaults
    if mattype == 'Principled':
        shader.parmTuple('basecolor').set((1,1,1))
        shader.parm('dispTex_offset').set(0)
    if mattype == 'Mtlx':
        shader.setMaterialFlag(True)


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

def createAsset(files, meta, cwd, path, pos, mattype):
    legacy = True
    sop = None
    matnet = None
    if cwd.type().name() == 'obj':
        sop = cwd.createNode('geo', os.path.basename(path))
        matnet = sop.createNode('matnet')
    elif cwd.childTypeCategory().name() == 'Sop':
        sop = cwd.createNode('subnet', os.path.basename(path))
        matnet = sop.createNode('matnet')
    elif cwd.childTypeCategory().name() == 'Lop':
        legacy = False
        comp_geo = cwd.createNode('componentgeometry', os.path.basename(path))
        comp_mat = comp_geo.createOutputNode('componentmaterial')
        comp_out = comp_mat.createOutputNode('componentoutput')
        mat_lib = cwd.createNode('materiallibrary')
        comp_mat.setInput(1, mat_lib)

        fbx = [f for f in files if f.endswith('.fbx')]
        comp_geo.parm('sourceinput').set(1)
        comp_geo.parm('source').set(os.path.abspath(fbx[0]))
        comp_geo.parm('sourceproxy').set(os.path.abspath(fbx[-1]))
        comp_geo.parm('sourcesimproxy').set(os.path.abspath(fbx[-1]))
        mat_lib.parm('matpathprefix').set('/ASSET/mtl/')
        mat, p = createMaterial(files, meta, mat_lib, path, pos, mattype, use_meta=False)
        cwd.layoutChildren((comp_geo, comp_mat, mat_lib, comp_out))

    if legacy:
        fbx = [f for f in files if f.endswith('.fbx')]
        sop.setPosition(pos)
        mat, p = createMaterial(files, meta, matnet, path, pos, mattype, use_meta=False)
        layout = []
        for fb in fbx:
            file_node = sop.createNode('file', os.path.basename(fb))
            file_node.parm('file').set(os.path.abspath(fb))
            xform = file_node.createOutputNode('xform')
            xform.parm('scale').set(0.01)
            apply_mat = xform.createOutputNode('material')
            relpath = hou.text.relpath(mat.path(), apply_mat.path())
            relpath = '.' + relpath if relpath.startswith('./') else relpath
            apply_mat.parm('shop_materialpath1').set(relpath)
            layout += [file_node, xform, apply_mat]
            if 'LOD0' in fb:
                apply_mat.setDisplayFlag(True)
                apply_mat.setRenderFlag(True)
        sop.layoutChildren(layout)
        pos = hou.Vector2(pos.x() + sop.size().x()*2, pos.y())
    return pos




def prepareMS(path, i, pos, cwd, mattype):
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
            shader ,pos = createMaterial(files, meta, cwd, path, pos, mattype)
        elif meta['semanticTags']['asset_type'] == '3D asset':
            pos = createAsset(files, meta, cwd, path, pos, mattype)
    return pos

def dropAccept(file_list):
    if len(file_list) == 1 and os.path.splitext(file_list[0])[1] == ".hip":
        return False

    panetab = hou.ui.paneTabUnderCursor()
    if isinstance(panetab, hou.NetworkEditor):
        pos = panetab.cursorPosition()
        cwd = panetab.pwd()
        types = ('Principled', 'Mtlx', 'Redshift')
        for i, path in enumerate(file_list):
            if os.path.isdir(path):
                if i == 0:
                    mode = hou.ui.displayMessage('Choose type', types)
                    mattype = types[mode]
                pos = prepareMS(path, i, pos, cwd, mattype)

            elif re.search(r'.*_Preview.png', path):
                if i == 0:
                    mode = hou.ui.displayMessage('Choose type', types)
                    mattype = types[mode]
                br = 1
                base, name = os.path.split(path)
                pattern = re.sub(r'_[a-zA-Z0-9]*_Preview.png', '.*', name)
                for d in os.listdir(base):
                    if os.path.isdir(os.path.join(base,d)) \
                        and re.search(pattern, d) and br:
                        pos = prepareMS(os.path.join(base,d), i, pos, cwd, mattype)
                        br = 0




    return True