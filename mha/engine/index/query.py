from typing import Optional, Union, Sequence
from mha.engine.core import Plugin
from mha.engine.home import Home, HomeRender, Room, Device


__all__ = ["Query"]



class Query(Plugin):
    Name: str = "query"
    Depends: Sequence[str] = ["home"]
    
    @property
    def _home(self) -> Home:
        return self.manager.get_plugin("home")

    def query_room(self) -> str:
        return "\n".join([HomeRender.render(Room, "detail", room, self._home) for room in self._home.rooms])

    def query_device(
        self,
        what: str,
        did: Optional[Union[str, Sequence[str]]] = None,
        spid: Optional[Union[str, Sequence[str]]] = None,
        category: Optional[Union[str, Sequence[str]]] = None,
        subcategory: Optional[Union[str, Sequence[str]]] = None,
        room: Optional[Union[str, Sequence[str]]] = None,
        tags: Optional[Union[str, Sequence[str]]] = None
    ) -> str:
        # check
        assert isinstance(what, str), f"what must be str, got {type(what)}"
        assert what in {"brief", "spec", "status", "spec_status"}, f"{what} is not a valid query, expected: brief, spec, status, spec-status"
            
        dids = set()
        if did is not None:
            assert isinstance(did, (str, tuple, list)), f"dpid must be str tuple or list, got {type(did)}"
            dids = {did} if isinstance(did, str) else set(did)

        spids = set()
        if spid is not None:
            assert isinstance(spid, (str, tuple, list)), f"spid must be str tuple or list, got {type(spid)}"
            spids = {spid} if isinstance(spid, str) else set(spid)

        categories = set()
        if category is not None:
            assert isinstance(category, (str, tuple, list)), f"category must be str tuple or list, got {type(category)}"
            categories = {category} if isinstance(category, str) else set(category)

        subcategories = set()
        if subcategory is not None:
            assert isinstance(subcategory, (str, tuple, list)), f"subcategory must be str tuple or list, got {type(subcategory)}"
            subcategories = {subcategory} if isinstance(subcategory, str) else set(subcategory)

        rooms = set()
        if room is not None:
            assert isinstance(room, (str, tuple, list)), f"room must be str tuple or list, got {type(room)}"
            rooms = {room} if isinstance(room, str) else set(room)

        tag_list = set()
        if tags is not None:
            assert isinstance(tags, (str, tuple, list)), f"tags must be str tuple or list, got {type(tags)}"
            tag_list = {tags} if isinstance(tags, str) else set(tags)

        # recall
        devices = []
        for device in self._home.devices:
            if len(dids) > 0 and device.did not in dids:
                continue
            if len(spids) > 0 and device.spid not in spids:
                continue
            if len(categories) > 0 and device.category not in categories:
                continue
            if len(subcategories) > 0 and device.subcategory not in subcategories:
                continue
            if len(rooms) > 0 and device.room not in rooms:
                continue
            if len(tag_list) > 0 and not any([tag in device.tags for tag in tag_list]):
                continue
            devices.append(device)


        # filter
        filter_devices = []
        if what == "spec":
            dev_spids = set()
            for device in devices:
                if device.spid in dev_spids:
                    continue
                dev_spids.add(device.spid)
                filter_devices.append(device)
        else:
            filter_devices = devices

        return "\n".join([HomeRender.render(Device, what, device, self._home) for device in filter_devices])

Plugin.register(Query)