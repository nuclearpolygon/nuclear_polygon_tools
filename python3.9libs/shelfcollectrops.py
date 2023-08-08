import hou


class NodeContainer():
    def __init__(self, content=None):
        self.content = content


class TraverseNode():
    no = -1
    sopNode = 0
    topNode = 1


class TreeNode(object):      
    def __init__(self, node, parents=[], pattern='', start=None, level=0, topnet=None, output=None):
        self.outputNode = output
        self.name = node.name()
        self.sopNode = node
        self.level = level
        self.pattern = pattern
        self.animated = self.__isAnimated()
        self.startTreeNode = start
        if start is None:
            self.startTreeNode = self
        self.parentTreeNodes = parents
        self.topNode = None
        self.topNetwork = topnet
        self.childrenTopNodes = []
        self.__checkTopnet()
        self.childrenTreeNodes = []
        self.childrenSopNodes = self.__findNext(self.sopNode)
        self.__parentSopNodes = self.__findPrev(self.sopNode)
        self.__id = id(self)
        
        # self.populateChildren()
        
    def __str__(self):
        return self.name
        
    def __repr__(self):
        return self.name

    # if top node with same name exists in topnet make it ours
    def __checkTopnet(self):
        if self.topNetwork is not None:
            for top_node in self.topNetwork.children():
                if self.name == top_node.name():
                    self.topNode = top_node
                    return
               
    def type(self):
        return 'TreeNode'
    
    def __sopDependents(self, sop_node):
        deps = sop_node.dependents(include_children=False)
        found = []
        for dep in deps:
            if dep in sop_node.children() or dep == sop_node:
                continue
            else:
                found += [dep]
        return found + list(sop_node.outputs())
    
    # find next child sop nodes matching pattern (i.e *filecache*)
    def __findNext(self, sop_node):
        stack = list(self.__sopDependents(sop_node))
        next_sops = []
        while stack:
            current_sop = stack.pop()
            if hou.text.patternMatch(self.pattern, current_sop.type().name()):
                if current_sop not in next_sops:
                    next_sops.append(current_sop)
            else:
                stack += self.__sopDependents(current_sop)

        return next_sops

    def __sopReferences(self, sop_node):
        deps = sop_node.references(include_children=False)
        found = []
        for dep in deps:
            if dep in sop_node.children() or dep == sop_node:
                continue
            else:
                found += [dep]
        return found + list(sop_node.inputs())

    # find previous parent sop nodes matching pattern (i.e *filecache*)
    def __findPrev(self, sop_node):
        stack = list(self.__sopReferences(sop_node))
        prev_sops = {}
        while stack:
            current_sop = stack.pop()
            if hou.text.patternMatch(self.pattern, current_sop.type().name()):
                if current_sop not in prev_sops:
                    prev_sops[current_sop.name()] = current_sop
            else:
                stack += self.__sopReferences(current_sop)
        return prev_sops
    
    def __isInTree(self, sop_node):
        queue = list(self.childrenTreeNodes)
        while queue:
            current_node = queue.pop(0)
            if current_node.sopNode == sop_node:
                return current_node
            else:
                queue += current_node.childrenTreeNodes
        return None
    
    def __isAnimated(self):
        return self.sopNode.parm('timedependent').eval() == 1 and self.sopNode.parm('trange').eval() == 1

    # create my own children. Called on initialization so 
    # leads to recursion as far it initializes
    # new TreeNode instances
    def populateChildren(self):
        processed = []
        for sop_node in self.childrenSopNodes:
            self.childrenTreeNodes += [TreeNode(sop_node, pattern=self.pattern, parents=[self], level=self.level+1, 
                    start=self, topnet=self.topNetwork, output=self.outputNode)]
        stack = list(self.childrenTreeNodes)

        while stack:
            current_node = stack.pop()
            next = self.__findNext(current_node.sopNode)
            for sop_child in next:
                in_tree = self.__isInTree(sop_child)
                if in_tree is None:
                    current_node.childrenTreeNodes += [TreeNode(sop_child, pattern=self.pattern, parents=[current_node],  
                    start=self, topnet=self.topNetwork, output=self.outputNode)]
                elif sop_child == in_tree.sopNode:
                    current_node.childrenTreeNodes += [in_tree]
            stack += current_node.childrenTreeNodes
            processed += [current_node]

    def populateTopnet(self):
        # make sure topNode is present
        self.__createTopNode()
        # if no children connect to output
        if self.childrenTreeNodes == [] and self.topNode not in self.outputNode.inputs():
            self.outputNode.setNextInput(self.topNode)
        self.__createRange()
        for child in self.childrenTreeNodes:
            child.processAsChild(self)
        # create children and connect them
        process_children = list(self.childrenTreeNodes)
        processed = []
        while process_children:
            tree_node = process_children.pop(0)
            if tree_node in processed:
                continue
            processed.append(tree_node)
            process_children += tree_node.childrenTreeNodes
            # if no children connect to output
            if tree_node.childrenTreeNodes == [] and tree_node.topNode not in self.outputNode.inputs():
                self.outputNode.setNextInput(tree_node.topNode)
                continue
            # process children
            for child in tree_node.childrenTreeNodes:
                child.processAsChild(tree_node)
        return 0

    def __setAvgPosition(self, node):
        parents = list(self.__parentSopNodes.values())
        positions = [n.position() for n in parents]
        avg_pos = hou.Vector2()
        for pos in positions:
            avg_pos += pos
        avg_pos /= len(positions)

        node.setPosition(avg_pos + hou.Vector2(0,-2))

    def processAsChild(self, parent):
        self.__createTopNode()
        isInOtherTree = list(self.__parentSopNodes.keys()) != [p.name for p in self.parentTreeNodes]

        # connect through partitioner
        if len(self.parentTreeNodes) > 1 or isInOtherTree: 
            if len(self.topNode.inputs()) == 0:
                partitioner = self.topNetwork.createNode('partitionbyframe')
                self.__setAvgPosition(partitioner)
            else:
                partitioner = self.topNode.input(0)
                if partitioner.type().name() == 'rangeextend':
                    partitioner = partitioner.input(0)
            if parent.topNode not in partitioner.inputs():
                partitioner.setNextInput(parent.topNode)
            
                if self.topNode.input(0) is not None:
                    if self.topNode.input(0).type().name() != 'rangeextend':
                        self.topNode.setInput(0, partitioner)
                else:
                    self.topNode.setInput(0, partitioner)

        # connect directly
        else:
            if self.topNode.input(0) is None:
                self.topNode.setInput(0, parent.topNode)
        self.__createRange(parent)
        return self
                    
    def __createTopNode(self):
        if self.topNode is None:
            self.topNode = self.topNetwork.createNode('ropfetch', self.name)
            self.topNode.setPosition(self.sopNode.position())
            self.topNode.parm('roppath').set(self.topNode.relativePathTo(self.sopNode))
            self.topNode.parm('pdg_cachemode').set(2)
            if self.sopNode.parm('cachesim') is not None:
                self.topNode.parm('batchall').set(self.sopNode.parm('cachesim')) 
        return self.topNode

    def __createRange(self, parent=None):
        rangeparm = 'newrange'
        isInOtherTree = list(self.__parentSopNodes.keys()) != [p.name for p in self.parentTreeNodes]
        # if I'm first generate range
        if self.parentTreeNodes == []:
            if self.topNode.input(0) is not None:
                return 0
            range_generate = self.topNetwork.createNode('rangegenerate')
            range_generate.setPosition(self.topNode.position() + hou.Vector2(0,+2))
            rangeparm = 'range'
        else:
            need_extend = False
            for parent_ in self.parentTreeNodes:
                need_extend = need_extend or \
                parent_.sopNode.parmTuple('f').eval() != self.sopNode.parmTuple('f').eval() or \
                self.animated != parent_.animated
            if need_extend and (self.topNode.input(0) == parent.topNode or \
                self.topNode.input(0) in parent.topNode.outputs()):
                if self.topNode.input(0) is not None:
                    if self.topNode.input(0).type().name() == 'rangeextend':
                        return 0
                range_generate = self.topNetwork.createNode('rangeextend')
                range_generate.setPosition(self.topNode.position() + hou.Vector2(0,+2))
            else:
                return 0
        if self.animated:
            range_generate.parmTuple(rangeparm).set(self.sopNode.parmTuple('f'))
        else:
            range_generate.parmTuple(rangeparm).deleteAllKeyframes()
            range_generate.parmTuple(rangeparm).set(hou.Vector3(1,1,1))
        range_generate.setInput(0, self.topNode.input(0))
        self.topNode.setInput(0, range_generate)
        return 0
                
    def traverse(self, step=0, vis=True, max_level=-1, traverse_node=TraverseNode.no, find=None):
        indent = '-'
        if max_level > -1 and self.level > max_level:
            return []
        if find is not None and (find.content == self.sopNode or find.content == self.topNode):
            find.content = self
            return []
        if traverse_node == TraverseNode.sopNode:
            next = [self.sopNode]
        elif traverse_node == TraverseNode.topNode:
            next = [self.topNode]
        else:
            next = [self]
        if vis:
            print(f'{indent*step}{self} level={self.level} {id(self)}')
        for c in self.childrenTreeNodes:
            next += c.traverse(step + 1, vis=vis, max_level=max_level, traverse_node=traverse_node, find=find)
        return next

def collectRops():
    # find current Sopnet
    tabs = hou.ui.currentPaneTabs()
    current_network = None
    for tab in tabs:
        if tab.type().name() == 'NetworkEditor':
            current_network = tab
            break
    main_node = current_network.pwd()
    if main_node.childTypeCategory().name() == 'Sop':
        
        # filter out rops and tops
        all_nodes = main_node.children()
        tops = []
        rops = []
        top_pattern = '*topnetmgr*'
        rop_pattern = '*filecache*'
        for node in all_nodes:
            if hou.text.patternMatch(top_pattern, node.type().name()):
                tops.append(node)
            if hou.text.patternMatch(rop_pattern, node.type().name()):
                rops.append(node)
        if len(tops) > 0:
            topnet = tops[0]
        else:
            topnet = main_node.createNode('topnetmgr')
            topnet.moveToGoodPosition()
        outputs = topnet.glob('out_cache')
        if outputs == ():
            output = topnet.createNode('partitionbyframe', 'out_cache')
            output.setDisplayFlag(True)
        else:
            output = outputs[0]
        # find rops with no ancestors
        firstTreeNodes = []
        for rop in rops:
            rop_inputs = [i for i in rop.inputAncestors() if hou.text.patternMatch(rop_pattern, i.type().name())]
            if rop_inputs == []:
                treeNode = TreeNode(rop, pattern=rop_pattern, topnet=topnet, output=output)
                firstTreeNodes.append(treeNode)
                treeNode.populateChildren()
                treeNode.populateTopnet()
        output.moveToGoodPosition()