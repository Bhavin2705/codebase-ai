export const MOCK_REPOSITORIES = [
  {
    id: "repo-1",
    name: "spring-projects/spring-petclinic",
    url: "https://github.com/spring-projects/spring-petclinic",
    language: "Java",
    indexedAt: "2026-08-05 14:30",
    status: "ready",
    stats: { files: 42, classes: 128, methods: 512 }
  }
];

export const MOCK_FILE_TREE = [
  {
    path: "src/main/java/org/springframework/samples/petclinic",
    type: "dir",
    children: [
      {
        path: "src/main/java/org/springframework/samples/petclinic/owner",
        type: "dir",
        children: [
          { name: "OwnerController.java", path: "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java", type: "file" },
          { name: "OwnerRepository.java", path: "src/main/java/org/springframework/samples/petclinic/owner/OwnerRepository.java", type: "file" },
          { name: "Owner.java", path: "src/main/java/org/springframework/samples/petclinic/owner/Owner.java", type: "file" },
          { name: "Pet.java", path: "src/main/java/org/springframework/samples/petclinic/owner/Pet.java", type: "file" }
        ]
      },
      {
        path: "src/main/java/org/springframework/samples/petclinic/system",
        type: "dir",
        children: [
          { name: "WelcomeController.java", path: "src/main/java/org/springframework/samples/petclinic/system/WelcomeController.java", type: "file" },
          { name: "CacheConfiguration.java", path: "src/main/java/org/springframework/samples/petclinic/system/CacheConfiguration.java", type: "file" }
        ]
      },
      {
        path: "src/main/java/org/springframework/samples/petclinic/vet",
        type: "dir",
        children: [
          { name: "VetController.java", path: "src/main/java/org/springframework/samples/petclinic/vet/VetController.java", type: "file" },
          { name: "VetRepository.java", path: "src/main/java/org/springframework/samples/petclinic/vet/VetRepository.java", type: "file" }
        ]
      }
    ]
  },
  { name: "README.md", path: "README.md", type: "file" },
  { name: "pom.xml", path: "pom.xml", type: "file" }
];

export const MOCK_STARTER_QUESTIONS = [
  "How does authentication & security authorization work in this repository?",
  "Explain the data repository persistence layer for Owner and Pet entities.",
  "Where are API endpoints handled for owner search and creation?",
  "How is caching configured across services?"
];

export const MOCK_CONVERSATIONS = [
  {
    id: "chat-1",
    repositoryId: "repo-1",
    question: "How does the owner search and creation controller work?",
    answer: `The owner management flow is orchestrated by **OwnerController**.

### Key Component Architecture:
1. **Creation Handling**: \`initCreationForm\` and \`processCreationForm\` manage the web form workflow for new \`Owner\` instances.
2. **Search & Lookup**: \`processFindForm\` handles paginated queries via \`OwnerRepository\`.

### Direct Source Evidence:
- **[OwnerController.java](cite:src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java#L52-L68)** handles form rendering and submission validation.
- **[OwnerRepository.java](cite:src/main/java/org/springframework/samples/petclinic/owner/OwnerRepository.java#L35-L48)** executes Spring Data JPA queries against PostgreSQL.`,
    citations: [
      {
        id: "c1",
        label: "OwnerController.java:52-68",
        filePath: "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java",
        startLine: 52,
        endLine: 68,
        symbol: "processCreationForm"
      },
      {
        id: "c2",
        label: "OwnerRepository.java:35-48",
        filePath: "src/main/java/org/springframework/samples/petclinic/owner/OwnerRepository.java",
        startLine: 35,
        endLine: 48,
        symbol: "findByLastName"
      }
    ],
    confidence: "high",
    execution_time_ms: 1140,
    thought_process: {
      query_type: "Targeted Code RAG",
      total_files_scanned: 42,
      contexts_retrieved: 2,
      contexts_analyzed: [
        "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java",
        "src/main/java/org/springframework/samples/petclinic/owner/OwnerRepository.java"
      ],
      execution_time_ms: 1140,
      keywords_extracted: ["owner", "search", "controller", "creation"],
      llm_engine: "NVIDIA NIM (meta/llama-3.1-70b-instruct)"
    }
  }
];

export const MOCK_CODE_FILES = {
  "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java": {
    path: "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java",
    language: "java",
    content: `package org.springframework.samples.petclinic.owner;

import java.util.List;
import java.util.Map;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.web.bind.WebDataBinder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.InitBinder;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.servlet.ModelAndView;

@Controller
public class OwnerController {

    private static final String VIEWS_OWNER_CREATE_OR_UPDATE_FORM = "owners/createOrUpdateOwnerForm";
    private final OwnerRepository owners;

    public OwnerController(OwnerRepository clinicService) {
        this.owners = clinicService;
    }

    @InitBinder
    public void setAllowedFields(WebDataBinder dataBinder) {
        dataBinder.setDisallowedFields("id");
    }

    @GetMapping("/owners/new")
    public String initCreationForm(Map<String, Object> model) {
        Owner owner = new Owner();
        model.put("owner", owner);
        return VIEWS_OWNER_CREATE_OR_UPDATE_FORM;
    }

    @PostMapping("/owners/new")
    public String processCreationForm(@Valid Owner owner, BindingResult result) {
        if (result.hasErrors()) {
            return VIEWS_OWNER_CREATE_OR_UPDATE_FORM;
        }

        this.owners.save(owner);
        return "redirect:/owners/" + owner.getId();
    }

    @GetMapping("/owners/find")
    public String initFindForm(Map<String, Object> model) {
        model.put("owner", new Owner());
        return "owners/findOwners";
    }

    @GetMapping("/owners")
    public String processFindForm(@RequestParam(defaultValue = "1") int page, Owner owner, BindingResult result,
            Model model) {
        if (owner.getLastName() == null) {
            owner.setLastName("");
        }

        Page<Owner> ownersResults = findPaginatedForOwnersLastName(page, owner.getLastName());
        if (ownersResults.isEmpty()) {
            result.rejectValue("lastName", "notFound", "not found");
            return "owners/findOwners";
        }

        if (ownersResults.getTotalElements() == 1) {
            owner = ownersResults.getContent().get(0);
            return "redirect:/owners/" + owner.getId();
        }

        return addPaginationModel(page, model, ownersResults);
    }
}
`
  },
  "src/main/java/org/springframework/samples/petclinic/owner/OwnerRepository.java": {
    path: "src/main/java/org/springframework/samples/petclinic/owner/OwnerRepository.java",
    language: "java",
    content: `package org.springframework.samples.petclinic.owner;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.repository.Repository;
import org.springframework.transaction.annotation.Transactional;

public interface OwnerRepository extends Repository<Owner, Integer> {

    @Transactional(readOnly = true)
    Owner findById(Integer id);

    void save(Owner owner);

    @Transactional(readOnly = true)
    Page<Owner> findByLastName(String lastName, Pageable pageable);
}
`
  }
};

export const MOCK_INDEXING_STAGES = [
  { id: 1, name: "Repository Access", status: "completed", detail: "Cloned spring-projects/spring-petclinic (3.4 MB)" },
  { id: 2, name: "Discovery", status: "completed", detail: "Scanned 42 source files (.java, .md, .xml)" },
  { id: 3, name: "Parsing", status: "completed", detail: "Extracted 128 symbols via Tree-sitter" },
  { id: 4, name: "Representation", status: "completed", detail: "Generated embeddings for classes & methods" },
  { id: 5, name: "Storage", status: "completed", detail: "Saved vectors in pgvector database" }
];
