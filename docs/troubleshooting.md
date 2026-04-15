(troubleshooting)=

# Troubleshooting

This page lists all errors that can occur when running the pipeline. Most of them can be easily solved. For some cases,
we recommend contacting the MultiplEYE team. Whenever you encounter an error, we ask you to check this list first and
try to follow the instructions.

Please note that this page is under construction. It will be continually updated. If you encounter an error that is not
on this list, please reach out.


---

```{eval-rst}
.. raw:: html

   <div class="faq-search-container">
       <input type="text" id="faq-search" placeholder="Search troubleshooting entries...">
   </div>
```


(errors_processing)=

## Processing Errors

:::{dropdown} ValueError: Raw data cannot be loaded as the folder for session XY does not contain the expected number of files. Please check and select overwrite.

This error means that there exists saved raw data for a session, but it does not contain the files for
all stimuli. This means that the last time the files were generated something went wrong or was interrupted.
In order to be sure, that now all files are correct, it is important to write all files again.
This can be done by changing the parameter `overwrite` to `True` in the configuration file. This will make
sure that all files are generated again, and the error should not occur anymore even without choosing overwrite.
:::


---

```{eval-rst}
.. raw:: html

   <div id="faq-no-results" class="faq-no-results" style="display: none;">
       No results found. Try a different search term.
   </div>
```

```{eval-rst}
.. raw:: html

   <div id="faq-fallback" class="faq-fallback">
       <em>If none of this works, maybe look on the <a href="../faq">FAQ</a> page for answers. Finally, you can reach out to the maintainers.</em>
   </div>
```
