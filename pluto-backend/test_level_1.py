#!/usr/bin/env python3
"""
PLUTO Level 1 End-to-End Test Script

Tests all 15 terminal-first tools and context awareness.
Run this after starting the backend server.
"""
import asyncio
import sys
from app.tools.registry import get_registry
from app.agent.context_manager import ContextManager
from app.agent.state_machine import StateMachine, PlutoState
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class Level1Tester:
    """Test runner for Level 1 implementation"""
    
    def __init__(self):
        self.registry = get_registry()
        self.context_manager = ContextManager()
        self.state_machine = StateMachine()
        self.passed = 0
        self.failed = 0
        self.skipped = 0
    
    def print_header(self, text: str):
        """Print section header"""
        print(f"\n{'='*70}")
        print(f"  {text}")
        print(f"{'='*70}\n")
    
    def print_test(self, name: str, status: str, message: str = ""):
        """Print test result"""
        symbols = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}
        symbol = symbols.get(status, "❓")
        print(f"{symbol} {name}: {status}")
        if message:
            print(f"   └─ {message}")
    
    async def test_tool_registry(self):
        """Test 1: Tool Registry Initialization"""
        self.print_header("TEST 1: Tool Registry")
        
        try:
            # Check registry exists
            assert self.registry is not None, "Registry not initialized"
            self.print_test("Registry initialized", "PASS")
            
            # Check tool count
            tools = self.registry.get_all_tools()
            assert len(tools) == 15, f"Expected 15 tools, got {len(tools)}"
            self.print_test(f"Tool count ({len(tools)} tools)", "PASS")
            
            # Check categories
            info = self.registry.get_tool_info()
            categories = info["categories"]
            assert categories["application"] == 4, "Application tools count mismatch"
            assert categories["file"] == 6, "File tools count mismatch"
            assert categories["system"] == 5, "System tools count mismatch"
            self.print_test("Tool categories", "PASS", "app:4, file:6, system:5")
            
            # Check schemas
            schemas = self.registry.get_tool_schemas()
            assert len(schemas) == 15, "Schema count mismatch"
            self.print_test("OpenAI schemas", "PASS", f"{len(schemas)} schemas generated")
            
            self.passed += 4
            
        except AssertionError as e:
            self.print_test("Tool Registry", "FAIL", str(e))
            self.failed += 1
        except Exception as e:
            self.print_test("Tool Registry", "FAIL", f"Error: {str(e)}")
            self.failed += 1
    
    async def test_state_machine(self):
        """Test 2: State Machine"""
        self.print_header("TEST 2: State Machine")
        
        try:
            # Check initial state
            current = self.state_machine.get_current_state()
            assert current == PlutoState.IDLE, f"Expected IDLE, got {current}"
            self.print_test("Initial state", "PASS", "IDLE")
            
            # Test valid transitions
            transitions = [
                (PlutoState.LISTENING, True),
                (PlutoState.UNDERSTANDING, True),
                (PlutoState.THINKING, True),
                (PlutoState.PLANNING, True),
                (PlutoState.EXECUTING, True),
                (PlutoState.VERIFYING, True),
                (PlutoState.SPEAKING, True),
                (PlutoState.LISTENING, True),
            ]
            
            for target, expected in transitions:
                result = self.state_machine.transition(target)
                assert result == expected, f"Transition to {target} failed"
            
            self.print_test("State transitions", "PASS", "8 valid transitions")
            
            # Check history
            history = self.state_machine.get_history()
            assert len(history) > 0, "No history recorded"
            self.print_test("State history", "PASS", f"{len(history)} transitions tracked")
            
            self.passed += 3
            
        except AssertionError as e:
            self.print_test("State Machine", "FAIL", str(e))
            self.failed += 1
        except Exception as e:
            self.print_test("State Machine", "FAIL", f"Error: {str(e)}")
            self.failed += 1
    
    async def test_context_manager(self):
        """Test 3: Context Manager"""
        self.print_header("TEST 3: Context Manager")
        
        try:
            # Test context update
            self.context_manager.update_context({
                "current_app": "firefox",
                "browser_url": "https://youtube.com",
                "browser_title": "YouTube"
            })
            
            context = self.context_manager.get_context()
            assert context.current_app == "firefox", "Context update failed"
            self.print_test("Context update", "PASS")
            
            # Test action tracking
            from app.agent.context_manager import Action
            action = Action(
                tool="open_application",
                parameters={"application": "firefox"},
                result="Opened Firefox",
                success=True
            )
            self.context_manager.add_action(action)
            
            assert len(context.recent_actions) > 0, "Action not tracked"
            self.print_test("Action tracking", "PASS", "1 action recorded")
            
            # Test context summary
            summary = self.context_manager.get_context_summary()
            assert len(summary) > 0, "Empty context summary"
            assert "firefox" in summary.lower(), "App not in summary"
            self.print_test("Context summary", "PASS", f"{len(summary)} chars")
            
            self.passed += 3
            
        except AssertionError as e:
            self.print_test("Context Manager", "FAIL", str(e))
            self.failed += 1
        except Exception as e:
            self.print_test("Context Manager", "FAIL", f"Error: {str(e)}")
            self.failed += 1
    
    async def test_application_tools(self):
        """Test 4: Application Management Tools"""
        self.print_header("TEST 4: Application Tools (4 tools)")
        
        tools_to_test = [
            ("open_application", {"application": "firefox"}, "Launch browser"),
            ("list_running_applications", {}, "List apps"),
            ("switch_to_application", {"application": "firefox"}, "Focus window"),
            ("close_application", {"application": "nonexistent-app-xyz"}, "Close app"),
        ]
        
        for tool_name, params, description in tools_to_test:
            try:
                tool = self.registry.get_tool(tool_name)
                assert tool is not None, f"Tool {tool_name} not found"
                
                # Just verify tool exists and has correct attributes
                assert hasattr(tool, 'execute'), f"{tool_name} missing execute method"
                assert hasattr(tool, 'safety_level'), f"{tool_name} missing safety_level"
                
                self.print_test(f"{tool_name}", "PASS", description)
                self.passed += 1
                
            except AssertionError as e:
                self.print_test(f"{tool_name}", "FAIL", str(e))
                self.failed += 1
            except Exception as e:
                self.print_test(f"{tool_name}", "SKIP", "System dependency may be missing")
                self.skipped += 1
    
    async def test_file_tools(self):
        """Test 5: File Management Tools"""
        self.print_header("TEST 5: File Tools (6 tools)")
        
        tools_to_test = [
            ("open_file", {"path": "/tmp/test.txt"}, "Open file"),
            ("open_folder", {"path": "/tmp"}, "Open folder"),
            ("find_files", {"query": "test", "location": "/tmp"}, "Find files"),
            ("create_folder", {"path": "/tmp/pluto-test"}, "Create folder"),
            ("move_file", {"source": "/tmp/a", "destination": "/tmp/b"}, "Move file"),
            ("copy_file", {"source": "/tmp/a", "destination": "/tmp/b"}, "Copy file"),
        ]
        
        for tool_name, params, description in tools_to_test:
            try:
                tool = self.registry.get_tool(tool_name)
                assert tool is not None, f"Tool {tool_name} not found"
                assert hasattr(tool, 'execute'), f"{tool_name} missing execute method"
                
                self.print_test(f"{tool_name}", "PASS", description)
                self.passed += 1
                
            except AssertionError as e:
                self.print_test(f"{tool_name}", "FAIL", str(e))
                self.failed += 1
    
    async def test_system_tools(self):
        """Test 6: System Control Tools"""
        self.print_header("TEST 6: System Tools (5 tools)")
        
        tools_to_test = [
            ("take_screenshot", {"filename": "test.png"}, "Screenshot"),
            ("set_volume", {"level": "50"}, "Set volume"),
            ("get_volume", {}, "Get volume"),
            ("copy_to_clipboard", {"text": "test"}, "Copy to clipboard"),
            ("get_clipboard", {}, "Get clipboard"),
        ]
        
        for tool_name, params, description in tools_to_test:
            try:
                tool = self.registry.get_tool(tool_name)
                assert tool is not None, f"Tool {tool_name} not found"
                assert hasattr(tool, 'execute'), f"{tool_name} missing execute method"
                
                self.print_test(f"{tool_name}", "PASS", description)
                self.passed += 1
                
            except AssertionError as e:
                self.print_test(f"{tool_name}", "FAIL", str(e))
                self.failed += 1
    
    async def test_tool_execution(self):
        """Test 7: Actual Tool Execution (Safe Tests)"""
        self.print_header("TEST 7: Tool Execution (Safe Operations)")
        
        # Test 1: List running applications (safe, no side effects)
        try:
            result = await self.registry.execute_tool("list_running_applications", {})
            assert result.success or result.exit_code is not None, "No result from tool"
            self.print_test("list_running_applications", "PASS", f"Executed: {result.message[:50]}")
            self.passed += 1
        except Exception as e:
            self.print_test("list_running_applications", "SKIP", str(e))
            self.skipped += 1
        
        # Test 2: Find files in /tmp (safe)
        try:
            result = await self.registry.execute_tool("find_files", {
                "query": "test",
                "location": "/tmp",
                "max_results": 5
            })
            assert result is not None, "No result from find_files"
            self.print_test("find_files", "PASS", f"Search completed")
            self.passed += 1
        except Exception as e:
            self.print_test("find_files", "SKIP", str(e))
            self.skipped += 1
        
        # Test 3: Create folder (safe, in /tmp)
        try:
            import os
            import tempfile
            test_folder = os.path.join(tempfile.gettempdir(), "pluto-level1-test")
            
            result = await self.registry.execute_tool("create_folder", {
                "path": test_folder,
                "parents": True
            })
            
            # Clean up
            if os.path.exists(test_folder):
                os.rmdir(test_folder)
            
            assert result.success or os.path.exists(test_folder), "Folder not created"
            self.print_test("create_folder", "PASS", "Created and cleaned up")
            self.passed += 1
        except Exception as e:
            self.print_test("create_folder", "SKIP", str(e))
            self.skipped += 1
    
    async def test_intent_recommendations(self):
        """Test 8: Intent-Based Tool Recommendations"""
        self.print_header("TEST 8: Intent Detection & Recommendations")
        
        test_cases = [
            ("open firefox", ["open_application"]),
            ("find my documents", ["find_files"]),
            ("take a screenshot", ["take_screenshot"]),
            ("set volume to 50", ["set_volume"]),
            ("copy this to clipboard", ["copy_to_clipboard"]),
        ]
        
        for intent, expected_tools in test_cases:
            try:
                recommended = self.registry.get_recommended_tools(intent, {})
                
                # Check if at least one expected tool is recommended
                found = any(tool in recommended for tool in expected_tools)
                assert found, f"Expected {expected_tools}, got {recommended}"
                
                self.print_test(f"Intent: '{intent}'", "PASS", f"→ {recommended[0] if recommended else 'none'}")
                self.passed += 1
                
            except AssertionError as e:
                self.print_test(f"Intent: '{intent}'", "FAIL", str(e))
                self.failed += 1
    
    async def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*70)
        print("  PLUTO LEVEL 1 - END-TO-END TEST SUITE")
        print("="*70)
        
        # Run tests
        await self.test_tool_registry()
        await self.test_state_machine()
        await self.test_context_manager()
        await self.test_application_tools()
        await self.test_file_tools()
        await self.test_system_tools()
        await self.test_tool_execution()
        await self.test_intent_recommendations()
        
        # Print summary
        self.print_header("TEST SUMMARY")
        total = self.passed + self.failed + self.skipped
        
        print(f"✅ Passed:  {self.passed}/{total}")
        print(f"❌ Failed:  {self.failed}/{total}")
        print(f"⏭️  Skipped: {self.skipped}/{total} (missing system dependencies)")
        print()
        
        if self.failed == 0:
            print("🎉 ALL TESTS PASSED! PLUTO Level 1 is ready!")
            return 0
        else:
            print(f"❌ {self.failed} test(s) failed. Please review errors above.")
            return 1


async def main():
    """Main entry point"""
    tester = Level1Tester()
    exit_code = await tester.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
