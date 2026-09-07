"""Pattern-based command matching - NO AI REQUIRED.

Replaces LLM inference with smart pattern matching for zero-cost operation.
Uses fuzzy matching, keyword detection, and entity extraction.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Any
from difflib import SequenceMatcher

from app.core.logging import get_logger

logger = get_logger(__name__)


class PatternMatcher:
    """Smart command matching without AI inference."""

    def __init__(self):
        # Command patterns with variations and keywords
        self.patterns = {
            # Screenshot commands
            "take_screenshot": {
                "keywords": ["screenshot", "capture", "snap", "picture", "screen", "print screen", "screen grab"],
                "priority": 10
            },
            
            # Clipboard commands
            "copy_to_clipboard": {
                "keywords": ["copy", "clipboard", "copy to clipboard", "save to clipboard"],
                "priority": 10,
                "requires_text": True
            },
            "get_clipboard": {
                "keywords": ["paste", "clipboard", "get clipboard", "read clipboard", "what's in clipboard"],
                "priority": 10
            },
            
            # Volume commands
            "set_volume": {
                "keywords": ["volume", "sound", "audio level"],
                "patterns": [
                    r"(?:set|change|make|adjust)?\s*volume\s*(?:to|at)?\s*(\d+)",
                    r"volume\s*(\d+)",
                ],
                "priority": 9,
                "extractor": "volume_level"
            },
            "get_volume": {
                "keywords": ["what's the volume", "current volume", "volume level", "check volume"],
                "priority": 9
            },
            
            # Browser commands
            "open_url": {
                "keywords": ["open", "go to", "navigate", "visit", "browse"],
                "patterns": [
                    r"(?:open|go to|visit|navigate to|browse)\s+(.+)",
                ],
                "priority": 8,
                "extractor": "url_or_site"
            },
            "browser_search": {
                "keywords": ["search", "find", "look for", "search for"],
                "patterns": [
                    r"search\s+(?:for\s+)?(.+?)(?:\s+on\s+(\w+))?$",
                    r"look for\s+(.+?)(?:\s+on\s+(\w+))?$",
                    r"find\s+(.+?)(?:\s+on\s+(\w+))?$",
                ],
                "priority": 8,
                "extractor": "search_query"
            },
            "browser_click": {
                "keywords": ["click", "select", "choose", "pick"],
                "patterns": [
                    r"(?:click|select|choose|pick)\s+(?:the\s+)?(\w+)\s+(?:one|video|link|result|item)",
                    r"(?:click|select|choose|pick)\s+(?:number\s+)?(\d+)",
                ],
                "priority": 8,
                "extractor": "click_target"
            },
            "browser_fullscreen": {
                "keywords": ["fullscreen", "full screen", "maximize browser"],
                "priority": 8
            },
            "browser_snapshot": {
                "keywords": ["browser screenshot", "page screenshot", "browser snap"],
                "priority": 8
            },
            "close_browser": {
                "keywords": ["close browser", "close chrome", "close firefox", "exit browser"],
                "priority": 8
            },
            
            # Application commands
            "open_application": {
                "keywords": ["open", "launch", "start", "run"],
                "patterns": [
                    r"(?:open|launch|start|run)\s+(.+)",
                ],
                "priority": 7,
                "extractor": "application_name"
            },
            "close_application": {
                "keywords": ["close", "quit", "exit", "kill"],
                "patterns": [
                    r"(?:close|quit|exit|kill)\s+(.+)",
                ],
                "priority": 7,
                "extractor": "application_name"
            },
            "switch_to_application": {
                "keywords": ["switch to", "go to", "focus", "switch"],
                "patterns": [
                    r"(?:switch to|go to|focus|switch)\s+(.+)",
                ],
                "priority": 7,
                "extractor": "application_name"
            },
            "list_running_applications": {
                "keywords": ["list apps", "running apps", "open apps", "what's running", "show apps"],
                "priority": 7
            },
            
            # File operations
            "create_file": {
                "keywords": ["create file", "new file", "make file"],
                "patterns": [
                    r"(?:create|new|make)\s+(?:a\s+)?file\s+(?:called|named)?\s*(.+)",
                ],
                "priority": 6,
                "extractor": "file_path"
            },
            "create_folder": {
                "keywords": ["create folder", "new folder", "make folder", "create directory", "mkdir"],
                "patterns": [
                    r"(?:create|new|make)\s+(?:a\s+)?(?:folder|directory)\s+(?:called|named)?\s*(.+)",
                ],
                "priority": 6,
                "extractor": "folder_path"
            },
            "read_file": {
                "keywords": ["read file", "show file", "open file", "display file", "cat"],
                "patterns": [
                    r"(?:read|show|display|cat|open)\s+(?:file\s+)?(.+)",
                ],
                "priority": 6,
                "extractor": "file_path"
            },
            "list_directory": {
                "keywords": ["list directory", "list files", "show files", "ls", "dir"],
                "patterns": [
                    r"(?:list|show|ls|dir)\s+(?:directory|files|folder)?\s*(.+)?",
                ],
                "priority": 6,
                "extractor": "directory_path"
            },
            "delete_file": {
                "keywords": ["delete file", "remove file", "rm"],
                "patterns": [
                    r"(?:delete|remove|rm)\s+(?:file\s+)?(.+)",
                ],
                "priority": 6,
                "extractor": "file_path"
            },
            
            # System commands
            "execute_command": {
                "keywords": ["run command", "execute", "terminal"],
                "patterns": [
                    r"(?:run|execute)\s+(?:command\s+)?(.+)",
                ],
                "priority": 5,
                "extractor": "shell_command"
            },
            "get_processes": {
                "keywords": ["list processes", "show processes", "ps", "running processes"],
                "priority": 5
            },
        }
        
        # Common website mappings (for URL extraction)
        self.known_sites = {
            "youtube": "https://www.youtube.com",
            "gmail": "https://mail.google.com",
            "google": "https://www.google.com",
            "facebook": "https://www.facebook.com",
            "twitter": "https://twitter.com",
            "github": "https://github.com",
            "linkedin": "https://www.linkedin.com",
            "reddit": "https://www.reddit.com",
            "stackoverflow": "https://stackoverflow.com",
            "wikipedia": "https://www.wikipedia.org",
            "amazon": "https://www.amazon.com",
            "netflix": "https://www.netflix.com",
            "spotify": "https://www.spotify.com",
            "whatsapp": "https://web.whatsapp.com",
            "instagram": "https://www.instagram.com",
        }
        
        # Number words to digits
        self.number_words = {
            "first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4,
            "1st": 0, "2nd": 1, "3rd": 2, "4th": 3, "5th": 4,
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        }
    
    def similarity(self, a: str, b: str) -> float:
        """Calculate similarity ratio between two strings (0.0 to 1.0)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def match_command(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Match user input to a command and extract parameters.
        
        Returns:
            Dict with 'command', 'arguments', and 'confidence' or None if no match
        """
        user_input_lower = user_input.lower().strip()
        
        # Try exact pattern matches first (highest confidence)
        for command, config in self.patterns.items():
            if "patterns" in config:
                for pattern in config["patterns"]:
                    match = re.search(pattern, user_input_lower, re.IGNORECASE)
                    if match:
                        args = self._extract_arguments(command, match, config, user_input)
                        if args is not None:
                            return {
                                "command": command,
                                "arguments": args,
                                "confidence": 0.95,
                                "method": "pattern"
                            }
        
        # Try keyword matching with fuzzy tolerance
        best_match = None
        best_score = 0.0
        
        for command, config in self.patterns.items():
            for keyword in config["keywords"]:
                # Direct substring match
                if keyword in user_input_lower:
                    score = 0.90 + (config.get("priority", 5) / 100)
                    if score > best_score:
                        best_score = score
                        best_match = (command, config, keyword)
                    continue
                
                # Fuzzy match (for typos)
                similarity = self.similarity(keyword, user_input_lower)
                if similarity > 0.75:  # 75% similarity threshold
                    score = similarity * 0.85 + (config.get("priority", 5) / 100)
                    if score > best_score:
                        best_score = score
                        best_match = (command, config, keyword)
        
        if best_match and best_score > 0.70:  # Minimum confidence threshold
            command, config, matched_keyword = best_match
            args = self._extract_arguments_from_context(
                command, config, user_input, matched_keyword
            )
            return {
                "command": command,
                "arguments": args,
                "confidence": best_score,
                "method": "keyword"
            }
        
        return None
    
    def _extract_arguments(
        self, 
        command: str, 
        regex_match: re.Match, 
        config: Dict, 
        user_input: str
    ) -> Optional[Dict[str, Any]]:
        """Extract arguments from regex match based on command type."""
        extractor = config.get("extractor")
        
        if extractor == "volume_level":
            try:
                level = int(regex_match.group(1))
                return {"level": max(0, min(100, level))}
            except (ValueError, IndexError):
                return None
        
        elif extractor == "url_or_site":
            target = regex_match.group(1).strip()
            url = self._normalize_url(target)
            return {"url": url}
        
        elif extractor == "search_query":
            query = regex_match.group(1).strip()
            site = None
            try:
                if regex_match.group(2):
                    site = regex_match.group(2).strip()
            except IndexError:
                pass
            
            result = {"query": query}
            if site:
                result["site"] = site
            return result
        
        elif extractor == "click_target":
            target = regex_match.group(1).strip().lower()
            # Convert number words to indices
            if target in self.number_words:
                return {"index": self.number_words[target]}
            # Direct number
            try:
                index = int(target)
                return {"index": index - 1 if index > 0 else 0}  # Convert 1-based to 0-based
            except ValueError:
                return {"selector": target}
        
        elif extractor in ["application_name", "file_path", "folder_path", "directory_path", "shell_command"]:
            value = regex_match.group(1).strip()
            
            # Map to appropriate parameter name
            param_map = {
                "application_name": "application",
                "file_path": "path",
                "folder_path": "path",
                "directory_path": "path",
                "shell_command": "command"
            }
            param_name = param_map.get(extractor, "value")
            return {param_name: value}
        
        return {}
    
    def _extract_arguments_from_context(
        self,
        command: str,
        config: Dict,
        user_input: str,
        matched_keyword: str
    ) -> Dict[str, Any]:
        """Extract arguments when matched via keyword (not regex pattern)."""
        user_input_lower = user_input.lower().strip()
        
        # Remove the matched keyword to get remaining context
        remaining = user_input_lower.replace(matched_keyword, "").strip()
        
        # Command-specific extraction logic
        if command == "open_url":
            if remaining:
                url = self._normalize_url(remaining)
                return {"url": url}
            return {}
        
        elif command == "browser_search":
            if remaining:
                # Remove common filler words
                query = remaining.replace("for", "").replace("on", "").strip()
                return {"query": query}
            return {}
        
        elif command == "open_application" or command == "close_application" or command == "switch_to_application":
            if remaining:
                return {"application": remaining}
            return {}
        
        elif command == "set_volume":
            # Look for numbers in the input
            numbers = re.findall(r'\d+', user_input)
            if numbers:
                level = int(numbers[0])
                return {"level": max(0, min(100, level))}
            return {}
        
        elif command == "browser_click":
            # Look for ordinal or number
            for word in remaining.split():
                if word in self.number_words:
                    return {"index": self.number_words[word]}
            numbers = re.findall(r'\d+', remaining)
            if numbers:
                index = int(numbers[0])
                return {"index": index - 1 if index > 0 else 0}
            return {}
        
        elif command in ["create_file", "create_folder", "read_file", "delete_file"]:
            if remaining:
                return {"path": remaining}
            return {}
        
        elif command == "list_directory":
            return {"path": remaining if remaining else "."}
        
        elif command == "execute_command":
            if remaining:
                return {"command": remaining}
            return {}
        
        return {}
    
    def _normalize_url(self, text: str) -> str:
        """Convert text to a proper URL."""
        text = text.strip()
        
        # Already a URL
        if text.startswith(("http://", "https://")):
            return text
        
        # Known site name
        text_lower = text.lower()
        for site_name, url in self.known_sites.items():
            if site_name in text_lower:
                return url
        
        # Looks like a domain
        if "." in text and " " not in text:
            return f"https://{text}"
        
        # Treat as search query
        return f"https://www.google.com/search?q={text.replace(' ', '+')}"
    
    def get_capabilities(self) -> List[str]:
        """Return list of all supported commands."""
        return sorted(self.patterns.keys())


# Singleton instance
pattern_matcher = PatternMatcher()
