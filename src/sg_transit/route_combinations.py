"""Read-only route provenance index, not a routing or timing algorithm.

Prefix nodes own contiguous ranges of original route IDs. Shared suffixes are
annotations only: they cannot be traversed independently of the selected prefix.
"""
from dataclasses import dataclass, field

from sg_transit.models import validate_route


@dataclass
class _Node:
    parent: int | None
    arc: tuple | None
    depth: int
    children: dict = field(default_factory=dict)
    terminal: list = field(default_factory=list)
    start: int = 0
    end: int = 0


def _integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f'Invalid {name}')
    return value


class CombinationIndex:
    PAGE_SIZE = 8
    MAX_NODES = 60
    STOP_PAGE_SIZE = 24

    def __init__(self, network, entries):
        self.network, self.nodes, self.roots = network, [], {}
        self.paths, self.route_ids = {}, []
        for identifier, route in entries:
            if identifier in self.paths:
                raise ValueError('Duplicate route ID')
            validate_route(route, network)
            key = (route.origin, route.destination)
            if key not in self.roots:
                self.roots[key] = self._node(None, None, 0)
            cursor, path = self.roots[key], []
            for leg in route.legs:
                service = network.services[leg.service_id]
                a, b = service.stops.index(leg.board_stop), service.stops.index(leg.alight_stop)
                for start, end in zip(service.stops[a:b], service.stops[a+1:b+1]):
                    arc = (service.id, start, end)
                    path.append(arc)
                    children = self.nodes[cursor].children
                    if arc not in children:
                        children[arc] = self._node(cursor, arc, len(path))
                    cursor = children[arc]
            self.paths[identifier] = tuple(path)
            self.nodes[cursor].terminal.append(identifier)
        for root in self.roots.values():
            self._ranges(root)

    def _node(self, parent, arc, depth):
        self.nodes.append(_Node(parent, arc, depth))
        return len(self.nodes)-1

    def _ranges(self, cursor):
        node = self.nodes[cursor]
        node.start = len(self.route_ids)
        self.route_ids.extend(node.terminal)
        for arc in sorted(node.children):
            self._ranges(node.children[arc])
        node.end = len(self.route_ids)

    def _path(self, cursor):
        path = []
        while self.nodes[cursor].parent is not None:
            path.append(self.nodes[cursor].arc)
            cursor = self.nodes[cursor].parent
        return tuple(reversed(path))

    def _common_end(self, cursor):
        while not self.nodes[cursor].terminal and len(self.nodes[cursor].children) == 1:
            cursor = next(iter(self.nodes[cursor].children.values()))
        return cursor

    def _stop(self, code):
        return dict(id=code, name=self.network.stops[code].name)

    def _segments(self, path, kind, previous=None):
        groups = []
        for arc in path:
            if groups and groups[-1][-1][0] == arc[0]:
                groups[-1].append(arc)
            else:
                groups.append([arc])
        result = []
        for arcs in groups:
            service = arcs[0][0]
            result.append(dict(kind=kind, service=service, start=self._stop(arcs[0][1]),
                end=self._stop(arcs[-1][2]), stop_count=len(arcs)+1,
                action='continue' if previous == service else 'board' if previous is None else 'transfer',
                _stops=[arcs[0][1]]+[arc[2] for arc in arcs]))
            previous = service
        return result

    def view(self, origin=None, destination=None, *, selection=None, choice_page=0,
             route_page=0, graph_page=0, expand=None, stop_page=0, inspect=None):
        for name, value in [('choice_page', choice_page), ('route_page', route_page),
                            ('graph_page', graph_page), ('stop_page', stop_page)]:
            _integer(value, name)
        selection = [] if selection is None else selection
        if not isinstance(selection, list) or len(selection) > 120:
            raise ValueError('Invalid branch selection')
        groups = [dict(origin=a, destination=b, origin_name=self.network.stops[a].name,
                       destination_name=self.network.stops[b].name,
                       count=self.nodes[root].end-self.nodes[root].start)
                  for (a, b), root in self.roots.items()]
        if not groups:
            if selection or expand is not None:
                raise ValueError('No branch available')
            return dict(groups=[], nodes=[], routes=[], compatible_count=0, choice_count=0,
                        hidden_choices=0, hidden_nodes=0, hidden_routes=0, displayed_nodes=0,
                        selection=[], terminal=True, expanded=None, inspected=None, reference_count=0)
        key = (origin, destination) if origin is not None or destination is not None else next(iter(self.roots))
        if key not in self.roots:
            raise ValueError('Endpoints are not in the default reference pool')
        cursor = self._common_end(self.roots[key])
        for branch in selection:
            _integer(branch, 'branch')
            # Only a child of the current frontier is a selectable branch.
            if branch not in self.nodes[cursor].children.values():
                raise ValueError('Branch is incompatible with the selected prefix')
            cursor = self._common_end(branch)
        node, prefix = self.nodes[cursor], self._path(cursor)
        compatible = self.route_ids[node.start:node.end]
        tails = [self.paths[rid][len(prefix):] for rid in compatible]
        suffix = []
        for arcs in zip(*(reversed(path) for path in tails)):
            if len({arc[1:] for arc in arcs}) != 1:
                break
            suffix.append(arcs[0])
        suffix = tuple(reversed(suffix))
        blocks = self._segments(prefix, 'prefix')
        choices = sorted(node.children.items())
        if choice_page and choice_page*self.PAGE_SIZE >= len(choices):
            raise ValueError('Choice page out of range')
        choice_blocks = {}
        shown_choices = choices[choice_page*self.PAGE_SIZE:(choice_page+1)*self.PAGE_SIZE]
        for arc, child in shown_choices:
            end, chain = child, [arc]
            # Stop compression at either a branch or a service change.
            while not self.nodes[end].terminal and len(self.nodes[end].children) == 1:
                next_arc, next_node = next(iter(self.nodes[end].children.items()))
                if next_arc[0] != arc[0] or (suffix and next_arc[1:] == suffix[0][1:]):
                    break
                chain.append(next_arc)
                end = next_node
            block = self._segments(chain, 'choice', prefix[-1][0] if prefix else None)[0]
            block.update(branch=child, count=self.nodes[child].end-self.nodes[child].start)
            physical_path = tuple(block['_stops'])
            option = {k: block[k] for k in ('service', 'action', 'branch', 'count')}
            if physical_path in choice_blocks:
                choice_blocks[physical_path]['options'].append(option)
            else:
                block['options'] = [option]
                choice_blocks[physical_path] = block
                blocks.append(block)
        if suffix:
            # Do not draw the same physical corridor both inside a visible
            # choice and again as a shared tail. Earlier decisions remain lazy.
            stops = [suffix[0][1]]+[arc[2] for arc in suffix]
            cut = max((stops.index(b['end']['id']) for b in choice_blocks.values()
                       if b['end']['id'] in stops), default=0)
            suffix = suffix[cut:]
        if suffix:
            # Share the physical corridor, but retain each original path's
            # service and arrival state. These annotations are not branch edges.
            aligned = [self.paths[rid][-len(suffix):] for rid in compatible]
            begin = 0
            while begin < len(suffix):
                end = begin+1
                while end < len(suffix) and all(path[end][0] == path[begin][0] for path in aligned):
                    end += 1
                variants = {}
                for rid, path in zip(compatible, aligned):
                    service = path[begin][0]
                    start = len(self.paths[rid])-len(suffix)+begin
                    previous = self.paths[rid][start-1][0] if start else None
                    action = 'continue' if previous == service else 'board' if previous is None else 'transfer'
                    entry = variants.setdefault(service, dict(service=service, count=0,
                        continue_count=0, transfer_count=0, board_count=0))
                    entry['count'] += 1
                    entry[action+'_count'] += 1
                arcs = suffix[begin:end]
                blocks.append(dict(kind='rejoin', service=arcs[0][0],
                    alternatives=[variants[s] for s in sorted(variants)],
                    start=self._stop(arcs[0][1]), end=self._stop(arcs[-1][2]),
                    action='path_dependent', stop_count=len(arcs)+1,
                    entry_states={k: sum(v[k] for v in variants.values())
                                  for k in ('continue_count', 'transfer_count', 'board_count')},
                    _members={service: [rid for rid, path in zip(compatible, aligned)
                                        if path[begin][0] == service] for service in variants},
                    _stops=[arcs[0][1]]+[arc[2] for arc in arcs]))
                begin = end
        for i, block in enumerate(blocks):
            block['id'] = i
        expansion = None
        if expand is not None:
            _integer(expand, 'expand')
            if expand >= len(blocks):
                raise ValueError('Unknown segment')
            codes = blocks[expand]['_stops']
            if stop_page*self.STOP_PAGE_SIZE >= len(codes):
                raise ValueError('Stop page out of range')
            expansion = dict(segment=expand, total=len(codes), page=stop_page,
                stops=[self._stop(s) for s in codes[stop_page*self.STOP_PAGE_SIZE:(stop_page+1)*self.STOP_PAGE_SIZE]])
        # Reserve the expansion budget even while collapsed so page boundaries
        # never move when opening a segment near the end of a page.
        capacity = self.MAX_NODES-self.STOP_PAGE_SIZE
        if graph_page and graph_page*capacity >= len(blocks):
            raise ValueError('Graph page out of range')
        shown = blocks[graph_page*capacity:(graph_page+1)*capacity]
        if expansion and expand not in [b['id'] for b in shown]:
            raise ValueError('Expanded segment is not on this graph page')
        references = compatible
        if inspect is not None:
            if not isinstance(inspect, dict) or not isinstance(inspect.get('service'), str):
                raise ValueError('Invalid service inspection')
            segment = _integer(inspect.get('segment'), 'inspection segment')
            if segment not in [b['id'] for b in shown] or inspect['service'] not in blocks[segment].get('_members', {}):
                raise ValueError('Service is not in the shared segment')
            references = blocks[segment]['_members'][inspect['service']]
        reference_count = len(references)
        if route_page and route_page*self.PAGE_SIZE >= reference_count:
            raise ValueError('Route page out of range')
        references = references[route_page*self.PAGE_SIZE:(route_page+1)*self.PAGE_SIZE]
        return dict(groups=groups, origin=key[0], destination=key[1], selection=selection,
            frontier=self._stop(prefix[-1][2] if prefix else key[0]),
            onboard=prefix[-1][0] if prefix else None, terminal=bool(node.terminal),
            compatible_count=len(compatible), routes=references, route_page=route_page,
            hidden_routes=reference_count-len(references), inspected=inspect, reference_count=reference_count,
            choice_count=len(choices),
            choice_page=choice_page, hidden_choices=len(choices)-len(shown_choices),
            nodes=[{k: v for k, v in block.items() if not k.startswith('_')} for block in shown],
            graph_page=graph_page, graph_pages=max(1, (len(blocks)+capacity-1)//capacity),
            hidden_nodes=len(blocks)-len(shown), expanded=expansion,
            displayed_nodes=len(shown)+(len(expansion['stops']) if expansion else 0))
