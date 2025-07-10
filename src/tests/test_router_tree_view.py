from typing import Any
from pyouter.app import App
from pyouter.router import Router

import json
import asyncio
import time


async def dummy_async(config, options):
    print("dummy async function")
    
def dummy_sync(config, options):
    print("dummy sync function")

class DummyClass:
    def __init__(self, value) -> None:
        self.value = value
    
    async def run(self, config, options) -> Any:
        self.config = config
        self.options = options
        await self.inner()
    
    async def inner(self):
        print(f"run DummyClass, {self.value}")
        await asyncio.sleep(1)
        print(f"dummy class object, self.options.debug:{self.options.debug}, sleep 1s")
        if self.options.debug:
            print(f'debug, {self.value}')
            
class DummyClass_Sync:
    def __init__(self, value) -> None:
        self.value = value
    
    def run(self, config, options) -> Any:
        self.config = config
        self.options = options
        self.inner()
    
    def inner(self):
        print(f"run DummyClass_Sync, {self.value}")
        time.sleep(1)
        print(f"dummy class object, self.options.debug:{self.options.debug}, sleep 1s")
        if self.options.debug:
            print(f'debug, {self.value}')

if __name__=="__main__":
    '''
    Usage:
        ## execute:
        * python test_router_tree_view.py complex.deep.nested.func
        * python test_router_tree_view.py complex.deep.nested.obj
        * python test_router_tree_view.py complex
        
        ## dump router path only:
        * python test_router_tree_view.py complex.deep -i
        * python test_router_tree_view.py complex.deep --inspect
        
        ## dump router path and execute:
        * python test_router_tree_view.py complex.deep -v
        * python test_router_tree_view.py complex.deep --view
    '''
    
    app = App(
        config={},
    )
    
    app.option(
        '-d', '--debug',
        dest='debug',
        action="store_true",
        help='debug'
    )
    
    # 构造一个丰富的Router树，包含多个层级和分支
    app.use(
        router=Router(
            complex=Router(
                deep=Router(
                    nested=Router(
                        func=dummy_async,
                        obj=DummyClass("world"),
                        obj2=DummyClass_Sync(5),
                        another=Router(
                            func2=dummy_sync,
                            obj3=DummyClass("test"),
                            obj4=DummyClass_Sync(10)
                        )
                    ),
                    level2=Router(
                        func3=dummy_async,
                        obj5=DummyClass("level2"),
                        nested2=Router(
                            func4=dummy_sync,
                            obj6=DummyClass_Sync(15)
                        )
                    )
                ),
                wide=Router(
                    branch1=Router(
                        func5=dummy_async,
                        obj7=DummyClass("branch1")
                    ),
                    branch2=Router(
                        func6=dummy_sync,
                        obj8=DummyClass_Sync(20),
                        nested3=Router(
                            func7=dummy_async,
                            obj9=DummyClass("nested3")
                        )
                    ),
                    branch3=Router(
                        func8=dummy_sync,
                        obj10=DummyClass_Sync(25)
                    )
                ),
                mixed=Router(
                    func9=dummy_async,
                    obj11=DummyClass("mixed"),
                    deep2=Router(
                        func10=dummy_sync,
                        obj12=DummyClass_Sync(30),
                        nested4=Router(
                            func11=dummy_async,
                            obj13=DummyClass("nested4")
                        )
                    )
                )
            ),
            simple=Router(
                func12=dummy_sync,
                obj14=DummyClass("simple")
            ),
            another=Router(
                deep3=Router(
                    func13=dummy_async,
                    obj15=DummyClass_Sync(35),
                    nested5=Router(
                        func14=dummy_sync,
                        obj16=DummyClass("nested5")
                    )
                ),
                wide2=Router(
                    func15=dummy_async,
                    obj17=DummyClass_Sync(40)
                )
            )
        )
    )
    
    app.run() 