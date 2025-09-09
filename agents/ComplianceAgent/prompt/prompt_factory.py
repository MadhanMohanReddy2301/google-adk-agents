"""
Provides PromptFactory for loading prompt templates from text and DOCX files,
and assembling them into a single prompt string for agents.
"""

import os
from docx import Document


class PromptFactory:
    """
    Factory for loading and assembling agent prompts.
    """

    def read_docx_file(self, file_path):
        """
        Extracts text from a DOCX file using python-docx.
        """
        try:
            doc = Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs]
            return "\n".join(paragraphs)
        except Exception as e:
            print(f"Error reading DOCX file {file_path}: {e}")
            return ""

    def load_prompt_content(self, file_name):
        """
        Reads the file content from the 'prompts' folder based on file extension.
        Supports '.txt' and '.docx' files.
        """
        if not file_name or file_name.strip() == "":
            raise Exception(f" {file_name} Not found")

        file_path = os.path.join("prompts", file_name)
        if not os.path.exists(file_path):
            raise Exception(f"File not found: {file_path}")

        _, extension = os.path.splitext(file_path)
        extension = extension.lower()
        if extension == ".txt":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading text file {file_path}: {e}")
                return ""
        elif extension == ".docx":
            return self.read_docx_file(file_path)
        else:
            print(f"Unsupported file type: {extension}")
            return ""

    def get_agent_prompt(self):
        """
        Loads base, business, and knowledge prompt templates from the prompt_library
        folder and concatenates them into a single full prompt string.
        """

        current_file_directory = os.path.dirname(os.path.abspath(__file__))
        prompt_library_folder = "prompt_library"
        # Retrieve file names for each prompt type.
        system_base_file = os.path.join(current_file_directory, prompt_library_folder, "SystemBasePrompt.txt")
        system_business_file = os.path.join(current_file_directory, prompt_library_folder, "SystemBusinessPrompt.txt")
        system_knowledge_file = os.path.join(current_file_directory, prompt_library_folder, "SystemKnowledgePrompt.txt")

        # Load content from each file.
        base_prompt_content = self.load_prompt_content(system_base_file)
        business_prompt_content = self.load_prompt_content(system_business_file)
        knowledge_prompt_content = self.load_prompt_content(system_knowledge_file)

        # Combine the prompt contents.
        full_prompt = "\n".join([
            base_prompt_content,
            business_prompt_content,
            knowledge_prompt_content
        ]).strip()

        return full_prompt


if __name__ == "__main__":
    print(PromptFactory().get_agent_prompt())