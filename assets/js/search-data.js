// get the ninja-keys element
const ninja = document.querySelector('ninja-keys');

// add the home and posts menu items
ninja.data = [{
    id: "nav-about",
    title: "About",
    section: "Navigation",
    handler: () => {
      window.location.href = "/";
    },
  },{id: "nav-research-projects",
          title: "Research Projects",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/research-projects/";
          },
        },{id: "nav-publications",
          title: "Publications",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/publications/";
          },
        },{id: "nav-seminar",
          title: "Seminar",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/seminar/";
          },
        },{id: "nav-tools",
          title: "Tools",
          description: "A growing collection of the tools I and my team made.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/tools/";
          },
        },{id: "tools-vocatt",
          title: 'VocaTT',
          description: "A web-based application for online vocabulary training and testing",
          section: "Tools",handler: () => {
              window.location.href = "/tools/2021-vocatt/";
            },},{id: "tools-awe",
          title: 'AWE',
          description: "An LLM-based AWE program for TOEFL Independent Writing",
          section: "Tools",handler: () => {
              window.location.href = "/tools/2023-awe/";
            },},{id: "tools-grammar-diagnosis",
          title: 'Grammar Diagnosis',
          description: "An online diagnostic grammar test",
          section: "Tools",handler: () => {
              window.location.href = "/tools/2023-grammar-diagnosis/";
            },},{id: "tools-vocqgen",
          title: 'VocQGen',
          description: "A vocabulary question generator",
          section: "Tools",handler: () => {
              window.location.href = "/tools/2024-vocqgen/";
            },},{id: "tools-genquest",
          title: 'GenQuest',
          description: "An LLM-powered text-adventure game for language learning",
          section: "Tools",handler: () => {
              window.location.href = "/tools/2025-gen-quest/";
            },},{
        id: 'social-email',
        title: 'email',
        section: 'Socials',
        handler: () => {
          window.open("mailto:%6A%75%64%79.%77%61%6E%67@%68%6F%73%65%69.%61%63.%6A%70", "_blank");
        },
      },{
        id: 'social-github',
        title: 'GitHub',
        section: 'Socials',
        handler: () => {
          window.open("https://github.com/judywq", "_blank");
        },
      },{
        id: 'social-scholar',
        title: 'Google Scholar',
        section: 'Socials',
        handler: () => {
          window.open("https://scholar.google.com/citations?user=Ftb5Q3EAAAAJ", "_blank");
        },
      },{
      id: 'light-theme',
      title: 'Change theme to light',
      description: 'Change the theme of the site to Light',
      section: 'Theme',
      handler: () => {
        setThemeSetting("light");
      },
    },
    {
      id: 'dark-theme',
      title: 'Change theme to dark',
      description: 'Change the theme of the site to Dark',
      section: 'Theme',
      handler: () => {
        setThemeSetting("dark");
      },
    },
    {
      id: 'system-theme',
      title: 'Use system default theme',
      description: 'Change the theme of the site to System Default',
      section: 'Theme',
      handler: () => {
        setThemeSetting("system");
      },
    },];
