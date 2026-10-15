# Academic References & Theoretical Grounding

## Spatio-Temporal Urban Mobility Lakehouse Platform
**Author:** Muhammad Daffa Wardana  
**Discipline:** Big Data Infrastructure & Spatio-Temporal Computing  
**Citation Standard:** American Psychological Association (APA) 7th Edition  

---

## 1. Primary Academic Foundations

### Discrete Global Grid Systems (DGGS) & Hexagonal Spatial Binning
1. **Sahr, K., White, D., & Kimerling, A. J. (2003).** Geodesic discrete global grid systems. *Cartography and Geographic Information Science*, 30(2), 121–134. https://doi.org/10.1559/152304003100011090
   * **Relevance:** Sahr et al. provide the foundational mathematical proof demonstrating that hexagonal cells minimize quantization error and spatial distortion compared to square or triangular grids. Hexagons maintain equidistant centroids to all six immediate neighbors, eliminating diagonal edge anomalies in spatial autocorrelation and clustering.

2. **Brodsky, I. (2018).** *H3: Uber’s Hexagonal Hierarchical Spatial Index*. Uber Engineering Technical Publications. https://www.uber.com/blog/h3/
   * **Relevance:** Technical specification of the H3 Discrete Global Grid System (DGGS) utilized in this project. Details the hierarchical aperture 7 subdivision on an icosahedron, integer coordinate representation, and fast bitwise neighbor lookups used for ride-hailing demand aggregation.

### Trajectory Mining & Spatio-Temporal Mobility Modeling
3. **Zheng, Y. (2015).** Trajectory data mining: An overview. *ACM Transactions on Intelligent Systems and Technology (TIST)*, 6(3), 1–41. https://doi.org/10.1145/2743025
   * **Relevance:** Landmark comprehensive survey outlining the end-to-end framework for GPS trajectory cleansing, speed outlier filtering, map-matching, origin-destination (OD) flow matrix extraction, and space-time pattern discovery.

4. **Güting, R. H., Böhlen, M. H., Erwig, M., Jensen, C. S., Lorentzos, N. A., Schneider, M., & Vazirgiannis, M. (2000).** A foundation for representing and querying moving objects: Database system concepts. *ACM Transactions on Database Systems (TODS)*, 25(1), 1–42. https://doi.org/10.1145/352958.352963
   * **Relevance:** Foundational database theory for spatio-temporal moving objects, defining formal algebras and data types for trajectories, point-in-time states, and time-parameterized spatial geometry.

### Spatial Bias & The Modifiable Areal Unit Problem (MAUP)
5. **Openshaw, S. (1984).** *The Modifiable Areal Unit Problem*. Concepts and Techniques in Modern Geography (CATMOG), 38, Geo Books, Norwich, UK.
   * **Relevance:** Outlines why arbitrary administrative boundaries (ZIP codes, municipal boroughs) distort spatial analytics through scale and zoning aggregation bias. Justifies the adoption of uniform geometric units (Uber H3 hexagons) as an objective spatial partition.

### Spatial Database Indexing & Geometric Objects
6. **Ramsey, P., Obe, R., & Hsu, L. (2020).** *PostGIS: Spatial and Geographic Objects for PostgreSQL*. Open Source Geospatial Foundation (OSGeo).
   * **Relevance:** Core reference for Generalized Search Tree (GIST) indexing, R-Tree hierarchical spatial access methods, and OGC-compliant spatial operations (`ST_DistanceSphere`, `ST_MakeLine`, `ST_Within`).

7. **Guttman, A. (1984).** R-trees: A dynamic index structure for spatial searching. *Proceedings of the 1984 ACM SIGMOD International Conference on Management of Data*, 47–57. https://doi.org/10.1145/602259.602266
   * **Relevance:** Theoretical foundation of the multi-dimensional bounding-box indexing tree powering PostGIS GIST indexes implemented in our serving layer.

### Micro-Mobility & Real-Time Open Data Systems
8. **NABSA (North American Bikeshare & Scootershare Association). (2024).** *General Bikeshare Feed Specification (GBFS) v3.0 Release*. MobilityData Consortium. https://gbfs.mobilitydata.org/
   * **Relevance:** Industry-standard specification for real-time open data streaming of smart micro-mobility networks, defining the JSON schema for live station statuses, dock depletion metrics, and GPS positioning.

---

## 2. Theoretical Mapping to Project Implementation

| Academic Paper | Key Theoretical Principle | Concrete Project Implementation |
| :--- | :--- | :--- |
| **Sahr et al. (2003)** | Uniform Neighbor Distance & Quantization Invariance | Hexagonal spatial binning at Resolution 8 (~460m) eliminating corner bias. |
| **Brodsky (2018)** | Hierarchical Multi-Resolution Aperture 7 Grid | Ingestion at Res 7 (Macro Borough), Res 8 (Neighborhood), and Res 9 (Street Block). |
| **Zheng (2015)** | Trajectory Segmentation & Anomaly Rejection | Filtering speeds outside \([0.5, 60.0]\) km/h and durations outside \([1, 180]\) min. |
| **Openshaw (1984)** | Elimination of MAUP Zoning Bias | Standardizing mobility reporting into uniform hexagonal prisms rather than ZIP codes. |
| **Guttman (1984)** | R-Tree Hierarchical Bounding Box Search | PostGIS `GIST` indexing on `pickup_geom`, `dropoff_geom`, and `flow_line_geom`. |
| **NABSA (2024)** | Real-Time Open Telemetry & Depletion Sensing | Ingesting live feeds for 2,519 NYC stations with auto-calculated utilization rates. |
