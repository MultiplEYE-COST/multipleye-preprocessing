(faq)=

# Frequently Asked Questions & Common Warnings and Errors

*Introductionary text, Introductionary text, Introductionary text, Introductionary text,
Introductionary text, Introductionary text ,Introductionary text, Introductionary text,
Introductionary text, Introductionary text, Introductionary text, Introductionary text.*

---

## Frequently Asked Questions

```{eval-rst}
.. raw:: html

   <div class="faq-search-container">
       <input type="text" id="faq-search" placeholder="Search FAQs...">
   </div>
```

(faq_general)=

### General

:::{dropdown} How do I set up the preprocessing pipeline?
:open:

*Content to be added. #installation*
:::

:::{dropdown} What are the system requirements for running the pipeline?

*Content to be added. Specify - link getting-started*
:::

:::{dropdown} How long does preprocessing typically take?

*Content to be added.* Plan with X time to...
:::

(faq_equipment)=

### Eye-Tracking Equipment

:::{dropdown} What eye-tracking equipment is supported?

*Content to be added.*
:::

:::{dropdown} What file formats does the pipeline accept?

*Content to be added.*
:::

:::{dropdown} How should I organise my raw data files?

*Content to be added.*
:::

(faq_troubleshooting)=

### Troubleshooting

:::{dropdown} Why is my preprocessing failing with a "missing XYZ" error?

*Content to be added.*
:::

:::{dropdown} How do I handle corrupted or incomplete data files?

*Content to be added.*
:::

*Add more specific errors from user requests.*

---

(common_warnings_errors)=

## Common Warnings and Errors

(warnings_data_quality)=

### Data Quality Warnings

:::{dropdown} High ratio of missing data points - what should I do?

*Content to be added.*
:::

:::{dropdown} Excessive number of blinks detected during recording

*Content to be added.*
:::

(errors_processing)=

### Processing Errors

:::{dropdown} ValueError: Invalid timestamp format

*Content to be added.*
:::

:::{dropdown} RuntimeError: Out of memory during large file processing

*Content to be added.*
:::

:::{dropdown} FileNotFoundError: Configuration file not found

*Content to be added.*
:::

(errors_configuration)=

### Configuration Errors

:::{dropdown} KeyError: Missing required setting in config file

*Content to be added.*
:::

:::{dropdown} TypeError: Invalid value for parameter X

*Content to be added.*
:::

---

```{eval-rst}
.. raw:: html

   <script>
   document.addEventListener('DOMContentLoaded', function() {
       var input = document.getElementById('faq-search');
       if (!input) return;

       input.addEventListener('input', function() {
           var filter = input.value.toLowerCase();
           var dropdowns = document.querySelectorAll('.sd-dropdown');

           dropdowns.forEach(function(dropdown) {
               var title = dropdown.querySelector('.sd-summary-text').textContent.toLowerCase();
               var body = dropdown.querySelector('.sd-summary-content').textContent.toLowerCase();
               var container = dropdown.closest('section');

               if (title.indexOf(filter) > -1 || body.indexOf(filter) > -1) {
                   container.style.display = '';
               } else if (filter === '') {
                   container.style.display = '';
               } else {
                   container.style.display = 'none';
               }
           });
       });
   });
   </script>

   <style>
   .faq-search-container {
       text-align: center;
       margin-bottom: 2rem;
   }
   #faq-search {
       width: 100%;
       max-width: 500px;
       padding: 0.75rem 1rem;
       font-size: 1rem;
       border: 2px solid #e0e0e0;
       border-radius: 8px;
       transition: border-color 0.3s;
   }
   #faq-search:focus {
       outline: none;
       border-color: #4a90d9;
   }
   </style>
```