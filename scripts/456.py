import hou
from pathlib import Path


def setContext(event):
	if event is hou.hipFileEventType.AfterLoad or event is hou.hipFileEventType.AfterSave:
		path = Path(hou.hipFile.path())
		hip_path = str(path)
		parents = path.parents
		shot_name = str(parents[0].stem)
		shot_path = str(parents[0])
		stage_name = str(parents[1].stem)
		stage_path = str(parents[1])
		project_name = str(parents[2].stem)
		project_path = str(parents[2])
		parts = list(path.parts)[:-1]
		parts[2] = 'cache'
		cache_path = str(Path().joinpath(*parts))
		hou.setContextOption('hip', hip_path)
		hou.setContextOption('cache', cache_path)
		hou.setContextOption('shot_name', shot_name)
		hou.setContextOption('project_name', project_name)
		hou.setContextOption('shot', shot_path)
		hou.setContextOption('project', project_path)
		hou.setContextOption('stage', stage_name)

if not setContext in hou.hipFile.eventCallbacks():
	hou.hipFile.addEventCallback(setContext)